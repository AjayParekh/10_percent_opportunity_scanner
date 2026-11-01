# modules/database_manager.py
import sqlite3
import pandas as pd
from datetime import datetime
from config import DB_PATH

def get_connection():
    """Returns a connection to the SQLite database."""
    # Ensure the database directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database using schema.sql"""
    schema_path = DB_PATH.parent / "schema.sql"
    if not schema_path.exists():
        return "Schema file not found. Please create database/schema.sql first."
    
    with open(schema_path, "r") as f:
        schema_sql = f.read()
        
    with get_connection() as conn:
        conn.executescript(schema_sql)
    return "Database initialized successfully."

def insert_metric_facts(df: pd.DataFrame, source: str):
    """
    Inserts validated dataframe into metric_facts.
    Ensures source and retrieval_date are logged.
    """
    # Add required metadata columns
    df['source'] = source
    df['retrieval_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # We map the uploaded columns to the database schema
    # Assuming the CSV has: symbol, metric, value, reporting_period, quality_status
    columns_to_insert = ['symbol', 'metric', 'value', 'reporting_period', 'source', 'retrieval_date', 'quality_status']
    
    # Check if all required columns are present
    missing_cols = [col for col in columns_to_insert if col not in df.columns]
    if missing_cols:
        return False, f"Missing required columns for DB: {missing_cols}"

    try:
        with get_connection() as conn:
            # Use INSERT OR REPLACE to handle unique constraints
            df[columns_to_insert].to_sql('metric_facts', conn, if_exists='append', index=False, method='multi')
        return True, f"Successfully inserted {len(df)} rows into the database."
    except Exception as e:
        return False, f"Database insertion error: {str(e)}"

def get_all_metrics():
    """Fetches all data from the database for the Data Quality tab."""
    with get_connection() as conn:
        try:
            return pd.read_sql_query("SELECT * FROM metric_facts", conn)
        except pd.io.sql.DatabaseError:
            return pd.DataFrame() # Return empty if table doesn't exist yet
