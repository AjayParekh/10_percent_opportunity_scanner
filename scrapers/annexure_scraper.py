# scrapers/annexure_scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from config import REQUEST_TIMEOUT, REQUEST_DELAY

def fetch_annexure_data(url: str) -> pd.DataFrame:
    """
    Fetches and parses data from TheAnnexure using requests and BeautifulSoup.
    """
    # 1. Respectful Request Headers (Rule 8)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 2. Rate Limiting
        time.sleep(REQUEST_DELAY)
        
        # 3. Make Request
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Raises an error for 4xx/5xx status codes

    except requests.exceptions.RequestException as e:
        # Handle HTTP errors properly (Rule 7)
        print(f"Error fetching data: {e}")
        return None

    # 4. Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # --- NOTE: This is a generic HTML table parser. ---
    # You will need to inspect TheAnnexure's HTML and update the tag names below.
    # For example, if the data is in <table id="financial-data">, update it here.
    
    data = []
    table = soup.find('table') # Finds the first table on the page
    if not table:
        print("No table found on the page. The site might use JavaScript.")
        return None

    rows = table.find_all('tr')
    # Skip the header row (assuming the first row is headers)
    for row in rows[1:]:
        cols = row.find_all(['td', 'th'])
        # Clean the text and extract values
        cols = [ele.text.strip() for ele in cols]
        
        if len(cols) >= 3:
            # Map these indices to your actual data structure
            symbol = cols[0]
            metric = cols[1]
            value_str = cols[2] if len(cols) > 2 else None
            reporting_period = cols[3] if len(cols) > 3 else "Unknown"
            
            # Handle missing values strictly (Rule 10)
            try:
                value = float(value_str) if value_str and value_str != '-' else None
            except ValueError:
                value = None

            quality_status = 'verified' if value is not None else 'missing'
            
            data.append({
                'symbol': symbol,
                'metric': metric,
                'value': value,
                'reporting_period': reporting_period,
                'quality_status': quality_status
            })

    if not data:
        return None
        
    return pd.DataFrame(data)
