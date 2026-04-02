import os
from dotenv import load_dotenv

load_dotenv()

# API Keys (SpotCrime is optional now - using local NCRB data)
SPOTCRIME_API_KEY = os.getenv("SPOTCRIME_API_KEY", "")  # ✅ Added (can be empty)
MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "")

# Paths
MODEL_PATH = "models/risk_predictor.pkl"
RISK_DATA_PATH = "data/mumbai_risk_grid.json"
NCRB_DATA_PATH = "data/ncrb_mumbai_crimes.csv"

# Defaults
DEFAULT_LAT = 19.0760
DEFAULT_LNG = 72.8777
RISK_RADIUS_KM = 0.5