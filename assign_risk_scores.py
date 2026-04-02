import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List
from datetime import datetime
from config import NCRB_DATA_PATH, RISK_DATA_PATH

class RiskScoreCalculator:
    """
    Calculates normalized risk scores (0.0-1.0) for Mumbai regions
    Combines: crime frequency + night multiplier + severity + population density
    """
    
    # Weights for final risk calculation
    WEIGHTS = {
        'crime_frequency': 0.35,    # How many crimes occur
        'night_multiplier': 0.30,   # How much worse at night
        'severity': 0.25,           # How dangerous the crimes are
        'population_density': 0.10  # More people = more potential victims
    }
    
    # Mumbai region coordinates (for map display)
    REGION_COORDS = {
        'Borivali': {'lat': 19.2307, 'lng': 72.8567},
        'Andheri': {'lat': 19.1136, 'lng': 72.8697},
        'Dadar': {'lat': 19.0176, 'lng': 72.8479},
        'Bandra': {'lat': 19.0596, 'lng': 72.8295},
        'Kurla': {'lat': 19.0728, 'lng': 72.8826},
        'Ghatkopar': {'lat': 19.0865, 'lng': 72.9081},
        'Powai': {'lat': 19.1176, 'lng': 72.9060},
        'Malad': {'lat': 19.1868, 'lng': 72.8483},
        'Colaba': {'lat': 18.9067, 'lng': 72.8147},
        'Fort': {'lat': 18.9320, 'lng': 72.8347},
        'Marine Lines': {'lat': 18.9432, 'lng': 72.8236},
    }
    
    # Approximate population density (people per km²)
    POPULATION_DENSITY = {
        'Colaba': 25000, 'Fort': 22000, 'Marine Lines': 20000,
        'Dadar': 18000, 'Bandra': 16000, 'Andheri': 15000,
        'Kurla': 14000, 'Ghatkopar': 13000, 'Borivali': 12000,
        'Malad': 11000, 'Powai': 8000,
    }
    
    # Crime severity weights
    CRIME_SEVERITY = {
        'assault': 1.0,
        'harassment': 0.9,
        'robbery': 0.95,
        'theft': 0.7,
        'chain_snatching': 0.8,
    }
    
    def __init__(self, crime_df: pd.DataFrame, night_profiles: List[Dict]):
        self.crime_df = crime_df
        self.night_profiles = {p['region']: p for p in night_profiles}
    
    def calculate_region_risk(self, region: str) -> Dict:
        """Calculate comprehensive risk score for a region"""
        region_data = self.crime_df[self.crime_df['Region'] == region]
        
        if region_data.empty:
            return self._default_risk(region)
        
        # 1. Crime frequency score (0-1)
        total_crimes = region_data['Count'].sum()
        max_crimes = self.crime_df.groupby('Region')['Count'].sum().max()
        freq_score = min(1.0, total_crimes / max_crimes) if max_crimes > 0 else 0.5
        
        # 2. Night risk multiplier (normalize to 0-1)
        night_profile = self.night_profiles.get(region, {})
        night_mult = night_profile.get('night_multiplier', 1.0)
        night_score = (night_mult - 1.0) / 1.0  # Normalize 1.0-2.0 → 0.0-1.0
        
        # 3. Severity score (weighted average)
        severity_score = sum(
            row['Count'] * self.CRIME_SEVERITY.get(row['Crime_Type'], 0.5)
            for _, row in region_data.iterrows()
        ) / max(1, total_crimes)
        
        # 4. Population density score (normalize)
        pop_density = self.POPULATION_DENSITY.get(region, 10000)
        max_density = max(self.POPULATION_DENSITY.values())
        pop_score = pop_density / max_density
        
        # 5. Combine with weights
        final_score = (
            self.WEIGHTS['crime_frequency'] * freq_score +
            self.WEIGHTS['night_multiplier'] * night_score +
            self.WEIGHTS['severity'] * severity_score +
            self.WEIGHTS['population_density'] * pop_score
        )
        
        # Clamp to 0.0-1.0
        final_score = max(0.0, min(1.0, final_score))
        
        # Get coordinates
        coords = self.REGION_COORDS.get(region, {'lat': 19.0760, 'lng': 72.8777})
        
        # Determine risk level
        if final_score >= 0.7:
            risk_level = 'critical'
        elif final_score >= 0.5:
            risk_level = 'high'
        elif final_score >= 0.3:
            risk_level = 'moderate'
        else:
            risk_level = 'low'
        
        return {
            'Latitude': coords['lat'],
            'Longitude': coords['lng'],
            'risk': round(final_score, 3),
            'area_name': region,
            'risk_level': risk_level,
            'breakdown': {
                'crime_frequency': round(freq_score, 3),
                'night_multiplier': round(night_mult, 2),
                'severity': round(severity_score, 3),
                'population_density': round(pop_score, 3),
            },
            'night_profile': night_profile,
            'total_crimes': int(total_crimes),
            'last_updated': datetime.now().isoformat()
        }
    
    def _default_risk(self, region: str) -> Dict:
        """Return default risk for unknown regions"""
        coords = self.REGION_COORDS.get(region, {'lat': 19.0760, 'lng': 72.8777})
        return {
            'Latitude': coords['lat'],
            'Longitude': coords['lng'],
            'risk': 0.5,
            'area_name': region,
            'risk_level': 'moderate',
            'breakdown': {},
            'night_profile': {},
            'total_crimes': 0,
            'last_updated': datetime.now().isoformat()
        }
    
    def generate_risk_grid(self, output_path: str) -> List[Dict]:
        """Generate complete risk grid for all regions"""
        regions = self.crime_df['Region'].unique()
        risk_grid = [self.calculate_region_risk(region) for region in regions]
        
        # Sort by risk score (highest first)
        risk_grid.sort(key=lambda x: x['risk'], reverse=True)
        
        # Save to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(risk_grid, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Generated risk grid: {output_path}")
        print(f"📊 Total regions: {len(risk_grid)}")
        
        # Summary
        critical = sum(1 for r in risk_grid if r['risk'] >= 0.7)
        high = sum(1 for r in risk_grid if 0.5 <= r['risk'] < 0.7)
        moderate = sum(1 for r in risk_grid if 0.3 <= r['risk'] < 0.5)
        low = sum(1 for r in risk_grid if r['risk'] < 0.3)
        
        print(f"🔴 Critical (≥0.7): {critical}")
        print(f"🟠 High (0.5-0.7): {high}")
        print(f"🟡 Moderate (0.3-0.5): {moderate}")
        print(f"🟢 Low (<0.3): {low}")
        
        return risk_grid
    
    def print_summary(self, risk_grid: List[Dict]):
        """Print human-readable summary"""
        print("\n" + "=" * 60)
        print("🗺️ MUMBAI RISK GRID SUMMARY")
        print("=" * 60)
        
        print("\n🔴 TOP 5 HIGHEST RISK REGIONS:")
        for i, region in enumerate(risk_grid[:5], 1):
            print(f"   {i}. {region['area_name']}: {region['risk']} ({region['risk_level']})")
        
        print("\n🟢 TOP 5 SAFEST REGIONS:")
        for i, region in enumerate(risk_grid[-5:], 1):
            print(f"   {i}. {region['area_name']}: {region['risk']} ({region['risk_level']})")
        
        print("\n📊 RISK DISTRIBUTION:")
        avg_risk = sum(r['risk'] for r in risk_grid) / len(risk_grid)
        print(f"   • Average risk score: {avg_risk:.3f}")
        print(f"   • Highest risk: {risk_grid[0]['area_name']} ({risk_grid[0]['risk']})")
        print(f"   • Lowest risk: {risk_grid[-1]['area_name']} ({risk_grid[-1]['risk']})")


def main():
    """Run risk score calculation"""
    print("🚀 Step 3: Assign Risk Scores")
    print("=" * 60)
    
    # Load crime data
    if not os.path.exists(NCRB_DATA_PATH):
        print(f"❌ Data file not found: {NCRB_DATA_PATH}")
        print("💡 Run fetch_ncrb_data.py first!")
        return
    
    print(f"📥 Loading crime data from {NCRB_DATA_PATH}...")
    crime_df = pd.read_csv(NCRB_DATA_PATH)
    print(f"✅ Loaded {len(crime_df)} records")
    
    # Load night profiles from Step 2
    night_profiles_path = 'data/night_risk_profiles.json'
    if not os.path.exists(night_profiles_path):
        print(f"❌ Night profiles not found: {night_profiles_path}")
        print("💡 Run analyze_night_risk.py first!")
        return
    
    print(f"📥 Loading night profiles from {night_profiles_path}...")
    with open(night_profiles_path, 'r') as f:
        night_profiles = json.load(f)
    print(f"✅ Loaded {len(night_profiles)} night profiles")
    
    # Calculate risk scores
    print("\n🔍 Calculating risk scores...")
    calculator = RiskScoreCalculator(crime_df, night_profiles)
    risk_grid = calculator.generate_risk_grid(RISK_DATA_PATH)
    
    # Print summary
    calculator.print_summary(risk_grid)
    
    print("\n" + "=" * 60)
    print("🎉 ALL STEPS COMPLETE!")
    print("=" * 60)
    print("\n📁 Files Created:")
    print(f"   ✅ {NCRB_DATA_PATH} (crime data)")
    print(f"   ✅ {night_profiles_path} (night analysis)")
    print(f"   ✅ {RISK_DATA_PATH} (final risk grid)")
    
    print("\n🚀 Next Steps:")
    print("   1. Train ML model: python train_model.py")
    print("   2. Start backend: python main.py")
    print("   3. Run Flutter app: flutter run")
    print("   4. Toggle heatmap in app! 🔥")
    
    return risk_grid


if __name__ == "__main__":
    main()