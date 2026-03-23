"""Configuration: API keys, constants, and platform fixes."""

import os
import sys

# Windows terminals default to cp1252 which breaks Unicode output (checkmarks, em dashes).
# Runs once here since every module imports config directly or transitively.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# Data directory: ~/.job-sniper/
DATA_DIR = os.path.join(os.path.expanduser("~"), ".job-sniper")
os.makedirs(DATA_DIR, exist_ok=True)

# Load .env from ~/.job-sniper/ first, then fall back to current working directory
load_dotenv(os.path.join(DATA_DIR, ".env"))
load_dotenv()  # cwd .env — won't overwrite keys already set

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
ZEROBOUNCE_API_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")

DB_PATH = os.path.join(DATA_DIR, "sniper.db")

HUNTER_MONTHLY_LIMIT = 25
ZEROBOUNCE_MONTHLY_LIMIT = 100

FOLLOWUP_1_DAYS = 4
FOLLOWUP_2_DAYS = 10
FOLLOWUP_3_DAYS = 7
