import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import sqlite3
import concurrent.futures
from datetime import datetime

# --- UPDATED HEADERS TO BYPASS GITHUB BLOCK ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
DB_FILE = "market_snapshot.db"

def get_companies():
    print("Fetching company list from TheAnnexure...")
    url = "https://theannexure.com/companies.html"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find('table')
        
        companies = []
        if table:
            rows = table.find_all('tr')
            for row in rows[1:]: 
                cols = row.find_all('td')
                if len(cols) > 1:
                    ticker = cols[1].text.strip()
                    link = cols[0].find('a')
                    if link and 'company/' in link.get('href', ''):
                        bse_code = link['href'].split('/')[-1].replace('.html', '')
                        companies.append({"ticker": ticker, "bse": bse_code})
        
        # LIMIT FOR TESTING (50 companies)
        return companies[:50] 
    except Exception as e:
        print(f"Error fetching list: {e}")
        return []

def fetch_data(comp):
    ticker = comp['ticker']
    bse = comp['bse']
    
    # Changed to standard Google Finance URL (more reliable than /beta/)
    gf_url = f"https://www.google.com/finance/quote/{ticker}:NSE"
    annex_url = f"https://theannexure.com/company/{bse}.html"
    
    price, pe, pb, roe, drop_52w = 0.0, "N/A", "N/A", "N/A", "N/A"
    
    # 1. Fetch Google Finance
    try:
        res = requests.get(gf_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Robust price finding methods
        price_el = soup.find(attrs={"data-last-price": True})
        if price_el:
            price = float(price_el["data-last-price"])
        else:
            price_el = soup.find(class_="YMlKec fxKbKc")
            if price_el:
                price = float(re.sub(r'[^\d.]', '', price_el.text))
            else:
                # Fallback: search for ₹ symbol
                for div in soup.find_all("div"):
                    if div.text and div.text.strip().startswith("₹") and len(div.text.strip()) < 15:
                        try:
                            price = float(re.sub(r'[^\d.]', '', div.text))
                            break
                        except:
                            pass
    except Exception as e:
        pass
    
    # 2. Fetch TheAnnexure
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
        pass
        
    print(f"Scraped {ticker}: Price={price}")
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
    print("Database created successfully: market_snapshot.db")
