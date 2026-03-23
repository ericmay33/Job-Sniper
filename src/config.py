"""Configuration: API keys from environment variables and constants."""

import os
from dotenv import load_dotenv

load_dotenv()

# API keys loaded from environment variables
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
ZEROBOUNCE_API_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sniper.db")

# Verification credit limits (free tier)
HUNTER_MONTHLY_LIMIT = 25
ZEROBOUNCE_MONTHLY_LIMIT = 100

# Follow-up timing (days)
FOLLOWUP_1_DAYS = 4
FOLLOWUP_2_DAYS = 10
FOLLOWUP_3_DAYS = 7
