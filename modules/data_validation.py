# modules/data_validation.py
import pandas as pd

def validate_annexure_frame(df: pd.DataFrame):
    """
    Validates the uploaded TheAnnexure dataframe.
    Expected columns: symbol, metric, value, reporting_period
    """
    # 1. Standardize column names (lowercase, strip spaces)
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    required_cols = ['symbol', 'metric', 'value', 'reporting_period']
    missing_required = [c for c in required_cols if c not in df.columns]
    
    if missing_required:
        return None, {"status": "error", "message": f"Missing columns: {missing_required}"}

    # 2. Data Quality Checks
    # If value is null/NaN, mark quality as 'missing'. Do NOT fill it.
    df['quality_status'] = df['value'].apply(lambda x: 'verified' if pd.notnull(x) else 'missing')
    
    # Ensure all necessary columns exist for database
    if 'quality_status' not in df.columns:
         df['quality_status'] = 'missing'

    # Drop rows where symbol or metric is completely blank
    df = df.dropna(subset=['symbol', 'metric'])
    
    report = {
        "status": "success",
        "total_rows": len(df),
        "missing_values_count": len(df[df['quality_status'] == 'missing'])
    }
    
    return df, report
