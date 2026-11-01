# config.py
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_IMPORTS = BASE_DIR / "data" / "imports"
DB_PATH = BASE_DIR / "database" / "scanner.db"

# Data source identifiers: TheAnnexure is the primary source. Never silently fallback if missing.
SOURCE_ANNEXURE = "TheAnnexure"
SOURCE_NSE = "NSE"
SOURCE_BSE = "BSE"
SOURCE_MANUAL = "manual_import"

# Request rate limits (seconds) to respect server loads
REQUEST_DELAY = 2.5
REQUEST_TIMEOUT = 15

# Scoring weights placeholders. Leave empty until project specifications are approved.
OPPORTUNITY_WEIGHTS = {}  
ENTRY_WEIGHTS = {}
