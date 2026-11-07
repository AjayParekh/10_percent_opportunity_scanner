import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import sqlite3
import concurrent.futures
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
DB_FILE = "market_snapshot.db"

def get_companies():
    print("Fetching company list...")
    url = "https://theannexure.com/companies.html"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find('table')
        companies = []
        if table:
            for row in table.find_all('tr')[1:]: 
                cols = row.find_all('td')
                if len(cols) > 1:
                    ticker = cols[1].text.strip()
                    link = cols[0].find('a')
                    if link and 'company/' in link.get('href', ''):
                        bse_code = link['href'].split('/')[-1].replace('.html', '')
                        companies.append({"ticker": ticker, "bse": bse_code})
        
        # TESTING: Limit to 50 companies. REMOVE [:50] LATER for 5000!
        return companies[:50] 
    except Exception as e:
        print(f"Error fetching list: {e}")
        return []

def fetch_data(comp):
    ticker = comp['ticker']
    bse = comp['bse']
    gf_url = f"https://www.google.com/finance/quote/{ticker}:NSE"
    annex_url = f"https://theannexure.com/company/{bse}.html"
    
    price, pe, pb, roe, drop_52w = 0.0, "N/A", "N/A", "N/A", "N/A"
    
    # --- 1. BULLETPROOF GOOGLE FINANCE PRICE ---
    try:
        res = requests.get(gf_url, headers=HEADERS, timeout=10)
        
        # Method A: Regex on the raw HTML source (Bypasses all bot blocks)
        match = re.search(r'data-last-price="([\d\.]+)"', res.text)
        if match:
            price = float(match.group(1))
        else:
            # Method B: BeautifulSoup fallback
            soup = BeautifulSoup(res.text, 'html.parser')
            price_el = soup.find(class_="YMlKec fxKbKc")
            if price_el:
                price = float(re.sub(r'[^\d.]', '', price_el.text))
            else:
                # Method C: Generic Rupee symbol search
                match = re.search(r'₹([\d,]+\.\d{2})', res.text)
                if match:
                    price = float(match.group(1).replace(',', ''))
                    
    except Exception as e:
        print(f"Price error for {ticker}: {e}")
    
    # --- 2. THEANNEXURE FUNDAMENTALS ---
    try:
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
    except Exception as e:
        print(f"Fundamental error for {ticker}: {e}")
        
    print(f"Scraped {ticker}: Price=₹{price}")
    return {"ticker": ticker, "price": price, "pe": pe, "pb": pb, "roe": roe, "drop_52w": drop_52w}

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
    companies = get_companies()
    print(f"Scraping {len(companies)} companies...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_data, companies))
        
    df = pd.DataFrame(results)
    df['score'] = df.apply(calculate_score, axis=1)
    
    conn = sqlite3.connect(DB_FILE)
    df.to_sql('daily_snapshot', conn, if_exists='replace', index=False)
    conn.close()
    print("Database created: market_snapshot.db")
