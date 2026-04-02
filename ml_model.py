import joblib
import pandas as pd
import numpy as np
import math
import os
from typing import Dict, List
from config import MODEL_PATH, RISK_DATA_PATH

class RiskPredictor:
    def __init__(self, model_path: str):
        self.model = None
        self.scaler = None
        self.is_loaded = False
        self.known_regions = []
        
        # ✅ Load model and scaler
        try:
            self.model = joblib.load(model_path)
            print(f"✅ Model loaded: {model_path}")
            
            # Load scaler (required for proper predictions)
            scaler_path = 'models/scaler.pkl'
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                print(f"✅ Scaler loaded: {scaler_path}")
            else:
                print(f"⚠️ Scaler not found: {scaler_path}")
            
            # Load known regions for nearest-neighbor fallback
            self._load_known_regions()
            
            self.is_loaded = True
            print(f"✅ RiskPredictor initialized with {len(self.known_regions)} known regions")
            
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            self.model = None
            self.scaler = None
            self.is_loaded = False
        
        # ✅ Updated feature names (matches training data)
        self.feature_names = [
            'latitude', 'longitude', 'hour_of_day', 'day_of_week',
            'crime_count_7d', 'crime_count_30d', 'night_crime_ratio',
            'lighting_score', 'foot_traffic', 'police_proximity', 'public_transport_access'
        ]
    
    def _load_known_regions(self):
        """Load known regions from risk grid for nearest-neighbor fallback"""
        try:
            if os.path.exists(RISK_DATA_PATH):
                import json
                with open(RISK_DATA_PATH, 'r') as f:
                    risk_grid = json.load(f)
                
                self.known_regions = [
                    {
                        'lat': r.get('Latitude', 0),
                        'lng': r.get('Longitude', 0),
                        'risk': r.get('risk', 0.5),
                        'area_name': r.get('area_name', 'Unknown')
                    }
                    for r in risk_grid
                ]
                print(f"📍 Loaded {len(self.known_regions)} known regions for fallback")
        except Exception as e:
            print(f"⚠️ Could not load known regions: {e}")
            self.known_regions = []
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _find_nearest_region(self, lat: float, lng: float) -> Dict:
        """Find nearest known region for fallback prediction"""
        if not self.known_regions:
            return {'risk': 0.5, 'distance_km': 999, 'area_name': 'Unknown'}
        
        min_distance = float('inf')
        nearest = None
        
        for region in self.known_regions:
            distance = self._haversine_distance(lat, lng, region['lat'], region['lng'])
            if distance < min_distance:
                min_distance = distance
                nearest = region
        
        return {
            'risk': nearest['risk'] if nearest else 0.5,
            'distance_km': min_distance,
            'area_name': nearest['area_name'] if nearest else 'Unknown'
        }
    
    def predict_risk(self, features: Dict) -> Dict:
        """
        Predict risk score for a location
        Uses ML model + nearest-neighbor fallback for unknown areas
        """
        lat = features.get('latitude', 0)
        lng = features.get('longitude', 0)
        
        # ✅ Fallback if model not loaded
        if not self.is_loaded:
            nearest = self._find_nearest_region(lat, lng)
            return {
                'risk_score': nearest['risk'],
                'risk_level': 'moderate',
                'confidence': 0.3,
                'fallback_reason': 'model_not_loaded',
                'nearest_region': nearest['area_name'],
                'distance_km': nearest['distance_km']
            }
        
        try:
            # ✅ Create feature vector (ensure all features present)
            feature_vector = [features.get(f, 0) for f in self.feature_names]
            features_df = pd.DataFrame([feature_vector], columns=self.feature_names)
            
            # ✅ Scale features (CRITICAL - model expects scaled input)
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features_df.values)
            else:
                features_scaled = features_df.values
            
            # ✅ Predict
            risk_prob = float(self.model.predict_proba(features_scaled)[0][1])
            confidence = float(np.max(self.model.predict_proba(features_scaled)))
            
            # ✅ Classify risk level
            if risk_prob < 0.25:
                risk_level = 'safe'
            elif risk_prob < 0.5:
                risk_level = 'moderate'
            elif risk_prob < 0.75:
                risk_level = 'high'
            else:
                risk_level = 'critical'
            
            # ✅ Check if location is far from known regions (apply fallback blend)
            nearest = self._find_nearest_region(lat, lng)
            fallback_info = {}
            
            if nearest['distance_km'] > 5:  # More than 5km from any known region
                # Blend ML prediction with nearest known region
                blend_weight = min(1.0, nearest['distance_km'] / 10)  # 0.5-1.0 blend
                blended_risk = (risk_prob * (1 - blend_weight * 0.3) + nearest['risk'] * blend_weight * 0.3)
                
                fallback_info = {
                    'fallback_applied': True,
                    'nearest_region': nearest['area_name'],
                    'distance_km': round(nearest['distance_km'], 2),
                    'blend_weight': round(blend_weight, 2),
                    'original_risk': round(risk_prob, 3),
                    'blended_risk': round(blended_risk, 3)
                }
                
                risk_prob = blended_risk
                confidence = confidence * (1 - blend_weight * 0.3)  # Reduce confidence for blended predictions
            else:
                fallback_info = {
                    'fallback_applied': False,
                    'nearest_region': nearest['area_name'],
                    'distance_km': round(nearest['distance_km'], 2)
                }
            
            return {
                'risk_score': round(risk_prob, 3),
                'risk_level': risk_level,
                'confidence': round(confidence, 3),
                'location': {'lat': lat, 'lng': lng},
                **fallback_info
            }
            
        except Exception as e:
            print(f"❌ Prediction error: {e}")
            # ✅ Graceful fallback on error
            nearest = self._find_nearest_region(lat, lng)
            return {
                'risk_score': nearest['risk'],
                'risk_level': 'moderate',
                'confidence': 0.3,
                'fallback_reason': 'prediction_error',
                'error': str(e),
                'nearest_region': nearest['area_name'],
                'distance_km': nearest['distance_km']
            }
    
    def predict_grid_risk(self, grid_points: List[Dict]) -> List[Dict]:
        """Predict risk for multiple grid points (for heatmap)"""
        results = []
        for i, point in enumerate(grid_points, 1):
            risk = self.predict_risk(point)
            results.append({
                'lat': point.get('latitude', point.get('lat', 0)),
                'lng': point.get('longitude', point.get('lng', 0)),
                **risk
            })
            
            # Progress indicator for large grids
            if i % 100 == 0 or i == len(grid_points):
                print(f"   📊 Predicted {i}/{len(grid_points)} grid points ({i/len(grid_points)*100:.0f}%)", end='\r')
        
        print()  # New line after progress
        return results
    
    def get_model_info(self) -> Dict:
        """Get model metadata and statistics"""
        if not self.is_loaded:
            return {'status': 'not_loaded'}
        
        return {
            'status': 'loaded',
            'model_type': type(self.model).__name__,
            'n_features': len(self.feature_names),
            'feature_names': self.feature_names,
            'known_regions': len(self.known_regions),
            'has_scaler': self.scaler is not None
        }