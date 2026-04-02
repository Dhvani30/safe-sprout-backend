import requests
from datetime import datetime, timedelta
from typing import Dict, List
from config import SPOTCRIME_API_KEY

class CrimeDataFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.spotcrime.com/v2/crimes"
    
    def fetch_recent_crimes(self, lat: float, lng: float, radius_km: float = 0.5, days: int = 30) -> Dict:
        try:
            params = {
                'lat': lat, 'lon': lng, 'radius': radius_km,
                'start_date': (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            }
            if self.api_key: params['api_key'] = self.api_key
            
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                crimes = response.json().get("crimes", [])
                last_7d = [c for c in crimes if self._is_within_days(c, 7)]
                return {'last_7_days': len(last_7d), 'last_30_days': len(crimes), 'incidents': crimes[:10]}
            return {'last_7_days': 0, 'last_30_days': 0, 'incidents': []}
        except:
            return {'last_7_days': 0, 'last_30_days': 0, 'incidents': []}
    
    def _is_within_days(self, crime: Dict, days: int) -> bool:
        try:
            crime_date = datetime.strptime(crime.get('date', ''), "%Y-%m-%d")
            return (datetime.now() - crime_date).days <= days
        except:
            return False