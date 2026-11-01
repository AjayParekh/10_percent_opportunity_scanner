# scrapers/annexure_scraper.py
"""
TheAnnexure Data Entry Point.

If automated scraping is unavailable, the only valid behavior for this module is:
1. Guide the user to place their exported CSV/Excel file into data/imports/.
2. Strictly validate column names, reporting periods, and data completeness.
3. Write to metric_facts with source fixed to TheAnnexure.
No "fallback to other websites" logic is executed.
"""
import pandas as pd
from config import SOURCE_ANNEXURE
from modules.data_validation import validate_annexure_frame

def load_from_import(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath) if filepath.endswith(".csv") else pd.read_excel(filepath)
    validated, report = validate_annexure_frame(df)
    # If 'report' contains missing fields, subsequent DB writes must use quality_status = 'missing'
    return validated, report
