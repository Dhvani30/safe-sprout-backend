# ✅ ADD 'Request' to this import line:
from fastapi import FastAPI, HTTPException, Query, Request  # ← Added Request here
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import math, json

from ml_model import RiskPredictor
from crime_data import CrimeDataFetcher
from config import SPOTCRIME_API_KEY, MODEL_PATH, RISK_DATA_PATH, RISK_RADIUS_KM
app = FastAPI(title="Safe Sprout Risk API")
# Allow CORS for mobile app
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for mobile app)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

risk_predictor = RiskPredictor(MODEL_PATH)
crime_fetcher = CrimeDataFetcher(SPOTCRIME_API_KEY)

with open(RISK_DATA_PATH, 'r') as f:
    risk_grid = json.load(f)

class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    hour: Optional[int] = None
    user_profile: str = "general"

@app.get("/health")
def health_check():
    return {"status": "ok", "model_loaded": risk_predictor.is_loaded}

@app.post("/predict/risk")
async def predict_risk(request: LocationRequest):
    try:
        crime_data = crime_fetcher.fetch_recent_crimes(request.latitude, request.longitude, RISK_RADIUS_KM, 30)
        features = {
            'latitude': request.latitude, 'longitude': request.longitude,
            'hour_of_day': request.hour or datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'crime_count_7d': crime_data['last_7_days'],
            'crime_count_30d': crime_data['last_30_days'],
            'lighting_score': 5.0, 'foot_traffic': 5.0,
            'police_proximity': 1.0, 'public_transport_access': 0.5,
        }
        risk_result = risk_predictor.predict_risk(features)
        return {"success": True, "data": {"location": {"lat": request.latitude, "lng": request.longitude}, "risk": risk_result, "crime_stats": crime_data}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/heatmap/data")
async def get_heatmap_data(
    bbox: str = Query(...),
    zoom: int = Query(10),
    grid_resolution: int = Query(80),
):
    try:
        # Parse bounding box
        min_lng, min_lat, max_lng, max_lat = map(float, bbox.split(','))
        
        # Generate grid points
        grid_points = _generate_grid(min_lat, max_lat, min_lng, max_lng, grid_resolution)
        
        # Calculate risk scores with Mumbai boundary masking
        results = []
        for point in grid_points:
            lat = point['latitude']
            lng = point['longitude']
            
            # ✅ MUMBAI BOUNDARY MASKING
            # Set risk to 0 (transparent) for areas outside Mumbai
            is_in_mumbai = _is_point_in_mumbai_boundary(lat, lng)
            
            if not is_in_mumbai:
                # Outside Mumbai - set very low risk (nearly transparent)
                risk_score = 0.0
                risk_level = 'safe'
            else:
                # Inside Mumbai - calculate actual risk
                min_distance = float('inf')
                risk_score = 0.5
                nearest_region = None
                
                for region in risk_grid:
                    dist = _haversine_distance(
                        lat, lng,
                        region['Latitude'], region['Longitude']
                    )
                    if dist < min_distance and dist < 3.0:
                        min_distance = dist
                        risk_score = region.get('risk', 0.5)
                        nearest_region = region
                
                # Add location-based variation for areas without data
                if risk_score == 0.5 and nearest_region is None:
                    if lat < 18.95:  # South Mumbai
                        risk_score = 0.65
                    elif lat < 19.05:  # Central
                        risk_score = 0.55
                    elif lat < 19.20:  # Western suburbs
                        risk_score = 0.50
                    else:  # Far suburbs
                        risk_score = 0.45
                
                # Determine risk level
                if risk_score >= 0.7:
                    risk_level = 'critical'
                elif risk_score >= 0.5:
                    risk_level = 'high'
                elif risk_score >= 0.3:
                    risk_level = 'moderate'
                else:
                    risk_level = 'low'
            
            results.append({
                "lat": lat,
                "lng": lng,
                "risk_score": round(risk_score, 3),
                "risk_level": risk_level,
            })
        
        return {
            "success": True,
            "data": results,
            "metadata": {
                "grid_points": len(results),
                "bbox": bbox,
                "resolution": grid_resolution,
            }
        }
        
    except Exception as e:
        print(f"❌ Heatmap error: {e}")
        raise HTTPException(status_code=500, detail=f"Heatmap generation failed: {str(e)}")


def _is_point_in_mumbai_boundary(lat: float, lng: float) -> bool:
    """
    Check if a point is within Mumbai's approximate boundary
    Returns True if inside Mumbai, False if outside (sea/other cities)
    """
    # ✅ Approximate Mumbai boundary polygon (simplified)
    # This excludes: Thane (north-east), Navi Mumbai (east), open sea (west/south)
    
    # South Mumbai boundary (exclude open sea south of Colaba)
    if lat < 18.90 and lng < 72.80:
        return False
    
    # Western boundary (exclude open sea)
    if lng < 72.75:
        return False
    
    # Eastern boundary (exclude Thane creek & Navi Mumbai)
    if lng > 72.98:
        return False
    
    # Northern boundary (exclude Vasai-Virar)
    if lat > 19.45:
        return False
    
    # North-East boundary (exclude Thane city)
    if lat > 19.20 and lng > 72.95:
        return False
    
    # South-East boundary (exclude Navi Mumbai)
    if lat < 19.00 and lng > 73.00:
        return False
    
    # ✅ Inside Mumbai boundary
    return True


@app.get("/risk/alerts")
async def get_risk_alerts(lat: float = Query(...), lng: float = Query(...), radius_km: float = Query(1.0)):
    try:
        alerts = []
        for point in risk_grid:
            distance = _haversine_distance(lat, lng, point['Latitude'], point['Longitude'])
            if distance <= radius_km:
                risk_score = point.get('risk', 0)
                if risk_score > 0.7:
                    alerts.append({"location": point.get('area_name', 'Unknown'), "risk_level": "critical" if risk_score > 0.85 else "high", "risk_score": risk_score, "distance_km": distance})
        alerts.sort(key=lambda x: x['risk_score'], reverse=True)
        return {"success": True, "data": alerts[:10]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _generate_grid(min_lat, max_lat, min_lng, max_lng, resolution):
    grid_points = []
    lat_step = (max_lat - min_lat) / resolution
    lng_step = (max_lng - min_lng) / resolution
    for i in range(resolution + 1):
        for j in range(resolution + 1):
            grid_points.append({'latitude': min_lat + (i * lat_step), 'longitude': min_lng + (j * lng_step)})
    return grid_points

def _haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat, delta_lng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)