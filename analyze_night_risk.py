import pandas as pd
import numpy as np
import json
from typing import Dict, List
from config import NCRB_DATA_PATH, RISK_DATA_PATH

class NightRiskAnalyzer:
    """
    Analyzes crime data to identify night-time risk patterns
    Night hours defined as: 8 PM (20:00) to 6 AM (06:00)
    """
    
    # Crime severity weights (higher = more dangerous, especially at night)
    CRIME_SEVERITY_WEIGHTS = {
        'assault': 1.0,
        'harassment': 0.9,
        'robbery': 0.95,
        'theft': 0.7,
        'chain_snatching': 0.8,
        'burglary': 0.85,
        'kidnapping': 1.0,
        'murder': 1.0,
        'rape': 1.0,
    }
    
    def __init__(self, crime_df: pd.DataFrame):
        self.crime_df = crime_df
    
    def calculate_night_risk_multiplier(self, region: str) -> float:
        """
        Calculate how much risk increases at night for a region
        Returns: multiplier (1.0 = same risk day/night, 2.0 = double risk at night)
        """
        region_data = self.crime_df[self.crime_df['Region'] == region]
        
        if region_data.empty:
            return 1.0
        
        # Use Night_Percentage from data if available
        if 'Night_Percentage' in region_data.columns:
            avg_night_pct = region_data['Night_Percentage'].mean()
            # Convert to multiplier: 0.68 → 1.68x night risk
            return round(1.0 + avg_night_pct, 2)
        
        # Fallback: calculate from Night_Count / Count
        total = region_data['Count'].sum()
        night = region_data['Night_Count'].sum()
        if total > 0:
            night_pct = night / total
            return round(1.0 + night_pct, 2)
        
        return 1.0
    
    def get_region_night_profile(self, region: str) -> Dict:
        """Get detailed night-risk profile for a region"""
        region_data = self.crime_df[self.crime_df['Region'] == region]
        
        if region_data.empty:
            return {
                'region': region,
                'total_crimes': 0,
                'night_multiplier': 1.0,
                'peak_night_crimes': [],
                'risk_category': 'unknown'
            }
        
        total_crimes = region_data['Count'].sum()
        night_crimes = region_data['Night_Count'].sum()
        night_multiplier = self.calculate_night_risk_multiplier(region)
        
        # Top crime types at night (by night count)
        top_night = (region_data
            .sort_values('Night_Count', ascending=False)
            .head(3)[['Crime_Type', 'Night_Count']]
            .to_dict('records')
        )
        
        # Categorize risk
        if night_multiplier < 1.4:
            risk_cat = 'low'
        elif night_multiplier < 1.6:
            risk_cat = 'moderate'
        elif night_multiplier < 1.8:
            risk_cat = 'high'
        else:
            risk_cat = 'critical'
        
        return {
            'region': region,
            'total_crimes': int(total_crimes),
            'night_crimes': int(night_crimes),
            'night_percentage': round(night_crimes / max(1, total_crimes), 3),
            'night_multiplier': night_multiplier,
            'peak_night_crimes': top_night,
            'risk_category': risk_cat
        }
    
    def analyze_all_regions(self) -> List[Dict]:
        """Analyze night risk for all regions in dataset"""
        regions = self.crime_df['Region'].unique()
        return [self.get_region_night_profile(r) for r in regions]
    
    def print_summary(self):
        """Print human-readable summary"""
        print("\n🌙 Night Risk Analysis Summary")
        print("=" * 50)
        
        profiles = self.analyze_all_regions()
        
        # Sort by night multiplier (highest first)
        profiles.sort(key=lambda x: x['night_multiplier'], reverse=True)
        
        print(f"\n🔴 High/Critical Night Risk ({sum(1 for p in profiles if p['risk_category'] in ['high', 'critical'])} regions):")
        for p in profiles:
            if p['risk_category'] in ['high', 'critical']:
                print(f"   • {p['region']}: {p['night_multiplier']}x multiplier ({p['night_percentage']:.1%} night crimes)")
        
        print(f"\n🟡 Moderate Night Risk ({sum(1 for p in profiles if p['risk_category'] == 'moderate')} regions):")
        for p in profiles:
            if p['risk_category'] == 'moderate':
                print(f"   • {p['region']}: {p['night_multiplier']}x multiplier")
        
        print(f"\n🟢 Low Night Risk ({sum(1 for p in profiles if p['risk_category'] == 'low')} regions):")
        for p in profiles:
            if p['risk_category'] == 'low':
                print(f"   • {p['region']}: {p['night_multiplier']}x multiplier")


def main():
    """Run night risk analysis"""
    print("🚀 Step 2: Night Risk Analysis")
    print("=" * 50)
    
    # Load crime data
    if not os.path.exists(NCRB_DATA_PATH):
        print(f"❌ Data file not found: {NCRB_DATA_PATH}")
        print("💡 Run fetch_ncrb_data.py first!")
        return
    
    print(f"📥 Loading data from {NCRB_DATA_PATH}...")
    crime_df = pd.read_csv(NCRB_DATA_PATH)
    print(f"✅ Loaded {len(crime_df)} records")
    
    # Analyze
    print("\n🔍 Analyzing night-time patterns...")
    analyzer = NightRiskAnalyzer(crime_df)
    analyzer.print_summary()
    
    # Save profiles for next step
    profiles = analyzer.analyze_all_regions()
    output_path = 'data/night_risk_profiles.json'
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"\n💾 Saved night profiles to: {output_path}")
    
    print("\n✅ Step 2 Complete!")
    print("   Next: Run assign_risk_scores.py")
    
    return analyzer


if __name__ == "__main__":
    import os
    main()