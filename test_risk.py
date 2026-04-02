from ml_model import RiskPredictor
predictor = RiskPredictor('models/risk_predictor.pkl')

data = {
    'latitude': 19.0728,
    'longitude': 72.8826,
    'hour_of_day': 22,
    'day_of_week': 5,
    'crime_count_7d': 12,
    'crime_count_30d': 47,
    'night_crime_ratio': 0.71,
    'lighting_score': 4.5,
    'foot_traffic': 6.2,
    'police_proximity': 1.8,
    'public_transport_access': 0.9
}

result = predictor.predict_risk(data)

print("\n? Test Prediction:")
print(f"   Risk Score: {result.get('risk_score')}")
print(f"   Risk Level: {result.get('risk_level')}")
print(f"   Confidence: {result.get('confidence')}")
print(f"   Nearest Region: {result.get('nearest_region')}")
print(f"   Distance: {result.get('distance_km')} km")
