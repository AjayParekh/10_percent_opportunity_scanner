import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import sqlite3
import concurrent.futures
import yfinance as yf

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
DB_FILE = "market_snapshot.db"

def get_companies():
    print("Fetching full company list from TheAnnexure...")
    url = "https://theannexure.com/companies.html"
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find('table')
        companies = []
        
        if table:
            for row in table.find_all('tr')[1:]: 
                cols = row.find_all('td')
                if len(cols) > 2:
                    ticker = cols[1].text.strip()
                    mc_text = cols[2].text.strip().replace('₹', '').replace('Cr', '').replace(',', '').strip()
                    try:
                        mc_val = float(mc_text)
                    except:
                        mc_val = 0.0
                        
                    link = cols[0].find('a')
                    if link and 'company/' in link.get('href', ''):
                        bse_code = link['href'].split('/')[-1].replace('.html', '')
                        companies.append({"ticker": ticker, "bse": bse_code, "market_cap": mc_val})
        
        # Sort by Market Cap descending and take Top 500
        companies = sorted(companies, key=lambda x: x['market_cap'], reverse=True)
        return companies[:500] 
    except Exception as e:
        print(f"Error fetching list: {e}")
        return []

def fetch_data(comp):
    ticker = comp['ticker']
    bse = comp['bse']
    annex_url = f"https://theannexure.com/company/{bse}.html"
    
    price, pe, pb, roe, drop_52w = 0.0, "N/A", "N/A", "N/A", "N/A"
    
    # --- 1. FETCH PRICE (yfinance) ---
    try:
        # NSE tickers require a .NS suffix
        ticker_yf = f"{ticker}.NS"
        stock = yf.Ticker(ticker_yf)
        # Fetch 1 day of data to get the latest close price
        hist = stock.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
    except Exception as e:
        print(f"yfinance error for {ticker}: {e}")
    
    # --- 2. FETCH FUNDAMENTALS (TheAnnexure) ---
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
        print(f"Annexure error for {ticker}: {e}")
        
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
    print(f"Found Top {len(companies)} companies. Starting scrape...")
    
    results = []
    # Using 10 workers for yfinance, it's very fast and reliable
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_data, companies))
        
    df = pd.DataFrame(results)
    df['score'] = df.apply(calculate_score, axis=1)
    
    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    df.to_sql('daily_snapshot', conn, if_exists='replace', index=False)
    conn.close()
    print("Database created successfully: market_snapshot.db")
