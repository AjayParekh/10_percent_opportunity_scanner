# daily_worker.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import sqlite3
import concurrent.futures
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DB_FILE = "market_snapshot.db"

def get_all_5000_tickers():
    # 1. Fetch the master list from TheAnnexure
    url = "https://theannexure.com/companies.html"
    res = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(res.content, 'html.parser')
    table = soup.find('table')
    
    tickers = []
    if table:
        rows = table.find_all('tr')
        for row in rows[1:]: # Skip header
            cols = row.find_all('td')
            if len(cols) > 1:
                ticker = cols[1].text.strip()
                # We need the BSE code for TheAnnexure (you might need to extract this from the link href)
                link = cols[0].find('a')
                if link and 'company/' in link.get('href', ''):
                    bse_code = link['href'].split('/')[-1].replace('.html', '')
                    tickers.append({"ticker": ticker, "bse": bse_code})
    return tickers

def fetch_live_data(comp):
    # Simplified scraper for the worker
    gf_url = f"https://www.google.com/finance/beta/quote/{comp['ticker']}:NSE"
    annex_url = f"https://theannexure.com/company/{comp['bse']}.html"
    
    price = 0.0
    pe, pb, roe, drop_52w = "N/A", "N/A", "N/A", "N/A"
    
    try:
        # Google Finance
        res = requests.get(gf_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        price_el = soup.find(class_="YMlKec fxKbKc")
        if price_el:
            price = float(re.sub(r'[^\d.]', '', price_el.text))
            
        # TheAnnexure
        res = requests.get(annex_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            pe, pb = pe_pb.group(1), pe_pb.group(2)
            
        for row in soup.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                label, val = cells[0].get_text(strip=True).lower(), cells[1].get_text(strip=True)
                if "return on equity" in label: roe = val
                elif "against 52-week high" in label: drop_52w = val
    except:
        pass
        
    return {
        "ticker": comp["ticker"], "price": price, "pe": pe, "pb": pb, "roe": roe, "drop_52w": drop_52w, "date": datetime.now().strftime("%Y-%m-%d")
    }

def calculate_score(row):
    score = 0
    try:
        if 0 < float(row['pb']) < 1.0: score += 4
        elif 1.0 <= float(row['pb']) < 1.5: score += 2
        if 0 < float(row['pe']) < 20: score += 2
        if float(row['drop_52w'].replace('%', '')) < -15: score += 3
        if float(row['roe'].replace('%', '')) > 15: score += 3
    except: pass
    return score

if __name__ == "__main__":
    print("Starting Daily Scraper...")
    companies = get_all_5000_tickers()
    print(f"Found {len(companies)} companies. Scraping started...")
    
    results = []
    # Use 20 threads to scrape faster
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_live_data, companies))
        
    df = pd.DataFrame(results)
    df['score'] = df.apply(calculate_score, axis=1)
    
    # Save to SQLite
    conn = sqlite3.connect(DB_FILE)
    df.to_sql('daily_snapshot', conn, if_exists='replace', index=False)
    conn.close()
    print("Daily Scrape Complete! Database updated.")
