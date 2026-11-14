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
                if len(cols) > 4:
                    ticker = cols[1].text.strip()
                    
                    sector = "Unknown"
                    for i in range(3, 6):
                        if len(cols) > i and len(cols[i].text.strip()) > 2:
                            sector = cols[i].text.strip()
                            break
                    
                    mc_text = cols[2].text.strip().replace('₹', '').replace('Cr', '').replace(',', '').strip()
                    try:
                        mc_val = float(mc_text)
                    except:
                        mc_val = 0.0
                        
                    link = cols[0].find('a')
                    if link and 'company/' in link.get('href', ''):
                        bse_code = link['href'].split('/')[-1].replace('.html', '')
                        companies.append({"ticker": ticker, "bse": bse_code, "market_cap": mc_val, "sector": sector})
        
        companies = sorted(companies, key=lambda x: x['market_cap'], reverse=True)
        # UPDATED TO 5000 COMPANIES
        return companies[:5000] 
    except Exception as e:
        print(f"Error fetching list: {e}")
        return []

def fetch_data(comp):
    ticker = comp['ticker']
    bse = comp['bse']
    sector = comp['sector']
    annex_url = f"https://theannexure.com/company/{bse}.html"
    
    price, pe, pb, book_value, roe, drop_52w = 0.0, "N/A", "N/A", 0.0, "N/A", "N/A"
    
    # 1. Fetch Price (yfinance)
    try:
        ticker_yf = f"{ticker}.NS"
        stock = yf.Ticker(ticker_yf)
        hist = stock.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
    except Exception:
        pass
    
    # 2. Fetch Fundamentals (TheAnnexure)
    try:
        res = requests.get(annex_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            pe, pb = pe_pb.group(1), pe_pb.group(2)
            
        bv_match = re.search(r"BV\s*₹\s*([\d,\.]+)", text)
        if bv_match:
            book_value = float(bv_match.group(1).replace(',', ''))
        else:
            for row in soup.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    if "book value" in cells[0].get_text(strip=True).lower():
                        bv_clean = re.sub(r'[^\d.]', '', cells[1].get_text(strip=True))
                        if bv_clean:
                            book_value = float(bv_clean)
            
        for row in soup.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                label, val = cells[0].get_text(strip=True).lower(), cells[1].get_text(strip=True)
                if "return on equity" in label: roe = val
                elif "against 52-week high" in label: drop_52w = val
    except Exception:
        pass
        
    return {"ticker": ticker, "price": price, "pe": pe, "pb": pb, "book_value": book_value, "roe": roe, "drop_52w": drop_52w, "sector": sector}

def calculate_score(row):
    score = 0
    sector = str(row['sector']).lower()
    
    try:
        pb = float(row['pb'])
        pe = float(row['pe'])
        roe = float(row['roe'].replace('%', ''))
        drop = float(row['drop_52w'].replace('%', ''))
        price = float(row['price'])
        bv = float(row['book_value'])
    except:
        return 0 

    implied_roe = 0.0
    if pb > 0 and pe > 0:
        implied_roe = (pb / pe) * 100

    if any(x in sector for x in ['bank', 'financial', 'nbfc', 'insurance']):
        if 0 < pb < 1.0: score += 4
        elif 1.0 <= pb < 1.5: score += 2
        if 0 < pe < 15: score += 2
        if roe > 15: score += 3
        if drop < -15: score += 3
        
    elif any(x in sector for x in ['metal', 'energy', 'oil', 'gas', 'mining', 'cement']):
        if 0 < pb < 1.0: score += 5  
        elif 1.0 <= pb < 1.5: score += 3
        if 0 < pe < 12: score += 2
        if drop < -20: score += 3 
        if roe > 10: score += 2
        
    elif any(x in sector for x in ['it', 'software', 'fmcg', 'consumer', 'pharma', 'health']):
        if 0 < pe < 30: score += 2
        if roe > 20: score += 5
        if drop < -10: score += 5
        
    else:
        if 0 < pb < 1.0: score += 4
        elif 1.0 <= pb < 1.5: score += 2
        if 0 < pe < 20: score += 2
        if drop < -15: score += 3
        if roe > 15: score += 3

    if bv > 0 and price > 0 and price < bv:
        score += 2 
        
    if implied_roe > 15.0 and roe > 15.0:
        score += 3
        
    return min(score, 18)

if __name__ == "__main__":
    companies = get_companies()
    print(f"Found Top {len(companies)} companies. Starting scrape...")
    
    results = []
    # Increased workers slightly to handle 5000 companies faster
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        results = list(executor.map(fetch_data, companies))
        
    df = pd.DataFrame(results)
    df['score'] = df.apply(calculate_score, axis=1)
    
    df = df[df['price'] > 0]
    
    conn = sqlite3.connect(DB_FILE)
    df.to_sql('daily_snapshot', conn, if_exists='replace', index=False)
    conn.close()
    print("Database created successfully: market_snapshot.db")
