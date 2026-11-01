import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import concurrent.futures
import os
from datetime import datetime

# --- 1. PAGE SETUP & UI LAYER ---
st.set_page_config(page_title="Opportunity Scanner", layout="wide", page_icon="🏛️")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-app: #0A0D12;
        --bg-panel: #12161D;
        --border-hairline: #232A35;
        --text-primary: #E7EAEE;
        --text-secondary: #8891A0;
        --accent-gold: #C6992F;
        --signal-green: #34D399;
        --signal-red: #F87171;
    }

    .stApp {
        background-color: var(--bg-app);
        font-family: 'IBM Plex Sans', sans-serif;
    }
    [data-testid="stHeader"] { background-color: transparent; }
    .block-container { padding-top: 2rem; max-width: 1400px; }

    .omc-eyebrow {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        color: var(--accent-gold);
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }
    .omc-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 700;
        font-size: 2.05rem;
        color: var(--text-primary);
        letter-spacing: -0.01em;
        margin: 0 0 0.35rem 0;
    }
    .omc-subtitle {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.95rem;
        color: var(--text-secondary);
        margin-bottom: 1.1rem;
    }
    
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border-hairline);
        border-radius: 3px;
    }
    
    div[data-testid="stMetric"] {
        background-color: var(--bg-panel);
        border: 1px solid var(--border-hairline);
        border-radius: 5px;
        padding: 15px;
    }
    div[data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.8rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--accent-gold) !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetricDelta"] {
        color: var(--text-primary) !important;
    }
    
    hr { border-color: var(--border-hairline) !important; }
    </style>
    """,
    unsafe_allow_html=True
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def robust_numeric_parse(val_str):
    if not val_str or pd.isna(val_str): return 0.0
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val_str).replace(',', '').strip())
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

# --- 2. SCRAPERS (Google Finance & TheAnnexure) ---
@st.cache_data(ttl=300)
def fetch_google_finance_live_data(ticker: str):
    url = f"https://www.google.com/finance/beta/quote/{ticker}:NSE?tab=financials"
    metrics = {"price_str": "N/A", "price_val": 0.0, "pct_change_str": "N/A", "abs_change_str": "N/A"}
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200: return metrics
        soup = BeautifulSoup(res.text, 'html.parser')
        
        price_el = soup.find(attrs={"data-last-price": True}) or soup.find(class_="YMlKec fxKbKc")
        if not price_el:
            for div in soup.find_all("div"):
                if div.text and div.text.strip().startswith("₹") and len(div.text.strip()) < 15:
                    price_el = div
                    break

        if price_el:
            metrics["price_str"] = price_el.text.strip()
            metrics["price_val"] = robust_numeric_parse(metrics["price_str"])

        full_text = re.sub(r'\s+', ' ', soup.get_text(separator=" "))

        change_pattern_pct_first = re.search(r'([+-]?\d+\.\d+)\s*%\s*\(\s*([+-]?[\d,]+\.\d+)\s*\)\s*1D', full_text)
        change_pattern_abs_first = re.search(r'\(\s*([+-]?[\d,]+\.\d+)\s*\)\s*([+-]?\d+\.\d+)\s*%\s*1D', full_text)

        pct_part, abs_part = None, None
        if change_pattern_pct_first:
            pct_part, abs_part = change_pattern_pct_first.group(1), change_pattern_pct_first.group(2)
        elif change_pattern_abs_first:
            abs_part, pct_part = change_pattern_abs_first.group(1), change_pattern_abs_first.group(2)

        if pct_part and abs_part:
            metrics["pct_change_str"] = f"{pct_part}%"
            metrics["abs_change_str"] = abs_part
        else:
            change_text = ""
            if price_el:
                parent = price_el.find_parent()
                if parent:
                    sibling_divs = parent.find_all(string=re.compile(r'%'))
                    if sibling_divs: change_text = sibling_divs[0].strip()
            if change_text:
                clean_text = change_text.replace("Today", "").replace("After hours", "").strip()
                extracted_metrics = re.findall(r'([+-]?\d+(?:\.\d+)?%?)', clean_text)
                if extracted_metrics: metrics["pct_change_str"] = extracted_metrics[0]
            
            try:
                if metrics["price_val"] > 0 and metrics["pct_change_str"] != "N/A":
                    raw_pct = float(re.sub(r'[^\d.-]', '', metrics["pct_change_str"]))
                    prev_close = metrics["price_val"] / (1 + (raw_pct / 100.0))
                    calculated_abs_change = metrics["price_val"] - prev_close
                    metrics["abs_change_str"] = f"{'+' if calculated_abs_change > 0 else ''}{calculated_abs_change:.2f}"
            except Exception: pass
    except Exception: pass
    return metrics


@st.cache_data(ttl=3600)
def fetch_annexure_all_details(bse_code: str):
    url = f"https://theannexure.com/company/{bse_code}.html"
    data = {}
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        mc = re.search(r"Market cap ₹([\d,\.]+) cr", text)
        if mc: data["Market Cap"] = f"₹{mc.group(1)} Cr"
        
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            data["P/E Ratio"] = f"{pe_pb.group(1)}×"
            data["P/B Ratio"] = f"{pe_pb.group(2)}×"
            
        eps = re.search(r"EPS ₹([\d\.]+)", text)
        if eps: data["EPS"] = f"₹{eps.group(1)}"
        
        bv = re.search(r"BV ₹([\d\.]+)", text)
        if bv: data["Book Value"] = f"₹{bv.group(1)}"

        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = re.sub(r'\s+', ' ', cells[0].get_text(strip=True))
                    val = re.sub(r'\s+', ' ', cells[1].get_text(strip=True))
                    if label and val and label.lower() not in ["metric", "ratio", "period"]:
                        if label not in data: data[label] = val
    except Exception: pass
    return data


# --- 3. APP HEADER ---
st.markdown(
    """
    <div class="omc-eyebrow">Institutional Coverage · Data Matrix</div>
    <div class="omc-title">🏛️ Opportunity Scanner & Tracker</div>
    <div class="omc-subtitle">Real-time scraped data. Over 100 companies tracked.</div>
    """,
    unsafe_allow_html=True
)

COMPANIES = [
    {"name": "Reliance Industries Ltd", "ticker": "RELIANCE", "bse": "500325", "industry": "Integrated Energy / O2C", "type": "Private"},
    {"name": "Bank of India", "ticker": "BANKINDIA", "bse": "532149", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "Tata Consultancy Services", "ticker": "TCS", "bse": "532540", "industry": "IT Services", "type": "Private"},
    {"name": "HDFC Bank Ltd", "ticker": "HDFCBANK", "bse": "500180", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "ICICI Bank Ltd", "ticker": "ICICIBANK", "bse": "532174", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Infosys Ltd", "ticker": "INFY", "bse": "500209", "industry": "IT Services", "type": "Private"},
    {"name": "Bharti Airtel Ltd", "ticker": "BHARTIARTL", "bse": "532454", "industry": "Telecom", "type": "Private"},
    {"name": "State Bank of India", "ticker": "SBIN", "bse": "500112", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "Life Insurance Corp of India", "ticker": "LICI", "bse": "543526", "industry": "Life Insurance", "type": "Government (PSU)"},
    {"name": "ITC Ltd", "ticker": "ITC", "bse": "500875", "industry": "FMCG", "type": "Private"},
    {"name": "Hindustan Unilever", "ticker": "HINDUNILVR", "bse": "500696", "industry": "FMCG", "type": "Private"},
    {"name": "Larsen & Toubro Ltd", "ticker": "LT", "bse": "500510", "industry": "Infrastructure", "type": "Private"},
    {"name": "Kotak Mahindra Bank", "ticker": "KOTAKBANK", "bse": "500247", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Axis Bank Ltd", "ticker": "AXISBANK", "bse": "532215", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Bajaj Finance Ltd", "ticker": "BAJFINANCE", "bse": "500034", "industry": "NBFC", "type": "Private"},
    {"name": "HCL Technologies Ltd", "ticker": "HCLTECH", "bse": "532281", "industry": "IT Services", "type": "Private"},
    {"name": "Maruti Suzuki India", "ticker": "MARUTI", "bse": "532500", "industry": "Automobiles", "type": "Private"},
    {"name": "Sun Pharmaceutical", "ticker": "SUNPHARMA", "bse": "524715", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Adani Enterprises Ltd", "ticker": "ADANIENT", "bse": "512599", "industry": "Infrastructure", "type": "Private"},
    {"name": "Titan Company Ltd", "ticker": "TITAN", "bse": "500114", "industry": "Consumer Goods", "type": "Private"},
    {"name": "Oil & Natural Gas Corp Ltd", "ticker": "ONGC", "bse": "500312", "industry": "Oil Exploration", "type": "Government (PSU)"},
    {"name": "NTPC Ltd", "ticker": "NTPC", "bse": "532555", "industry": "Power Generation", "type": "Government (PSU)"},
    {"name": "Power Grid Corp of India", "ticker": "POWERGRID", "bse": "532898", "industry": "Power Transmission", "type": "Government (PSU)"},
    {"name": "Tata Motors Ltd", "ticker": "TATAMOTORS", "bse": "500570", "industry": "Automobiles", "type": "Private"},
    {"name": "Coal India Ltd", "ticker": "COALINDIA", "bse": "533278", "industry": "Mining", "type": "Government (PSU)"},
    {"name": "UltraTech Cement Ltd", "ticker": "ULTRACEMCO", "bse": "532538", "industry": "Cement", "type": "Private"},
    {"name": "Adani Ports & SEZ", "ticker": "ADANIPORTS", "bse": "532921", "industry": "Ports", "type": "Private"},
    {"name": "Asian Paints Ltd", "ticker": "ASIANPAINT", "bse": "500820", "industry": "Paints", "type": "Private"},
    {"name": "Bajaj Finserv Ltd", "ticker": "BAJAJFINSV", "bse": "532978", "industry": "Financial Services", "type": "Private"},
    {"name": "Nestle India Ltd", "ticker": "NESTLEIND", "bse": "500790", "industry": "FMCG", "type": "Private"},
    {"name": "Wipro Ltd", "ticker": "WIPRO", "bse": "507685", "industry": "IT Services", "type": "Private"},
    {"name": "Tech Mahindra Ltd", "ticker": "TECHM", "bse": "532755", "industry": "IT Services", "type": "Private"},
    {"name": "Grasim Industries Ltd", "ticker": "GRASIM", "bse": "500300", "industry": "Diversified", "type": "Private"},
    {"name": "JSW Steel Ltd", "ticker": "JSWSTEEL", "bse": "500228", "industry": "Steel", "type": "Private"},
    {"name": "Hindalco Industries", "ticker": "HINDALCO", "bse": "500440", "industry": "Aluminium", "type": "Private"},
    {"name": "Tata Steel Ltd", "ticker": "TATASTEEL", "bse": "500470", "industry": "Steel", "type": "Private"},
    {"name": "Dr Reddy's Laboratories", "ticker": "DRREDDY", "bse": "500124", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Cipla Ltd", "ticker": "CIPLA", "bse": "500087", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Divi's Laboratories", "ticker": "DIVISLAB", "bse": "532488", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Apollo Hospitals", "ticker": "APOLLOHOSP", "bse": "508869", "industry": "Healthcare", "type": "Private"},
    {"name": "Mahindra & Mahindra", "ticker": "M&M", "bse": "500520", "industry": "Automobiles", "type": "Private"},
    {"name": "Bajaj Auto Ltd", "ticker": "BAJAJ-AUTO", "bse": "532977", "industry": "Automobiles", "type": "Private"},
    {"name": "Hero MotoCorp Ltd", "ticker": "HEROMOTOCO", "bse": "500182", "industry": "Automobiles", "type": "Private"},
    {"name": "Eicher Motors Ltd", "ticker": "EICHERMOT", "bse": "505200", "industry": "Automobiles", "type": "Private"},
    {"name": "Britannia Industries", "ticker": "BRITANNIA", "bse": "500825", "industry": "FMCG", "type": "Private"},
    {"name": "Dabur India Ltd", "ticker": "DABUR", "bse": "500096", "industry": "FMCG", "type": "Private"},
    {"name": "Godrej Consumer Products", "ticker": "GODREJCP", "bse": "532424", "industry": "FMCG", "type": "Private"},
    {"name": "Marico Ltd", "ticker": "MARICO", "bse": "531642", "industry": "FMCG", "type": "Private"},
    {"name": "UPL Ltd", "ticker": "UPL", "bse": "512070", "industry": "Agrochemicals", "type": "Private"},
    {"name": "Shree Cement Ltd", "ticker": "SHREECEM", "bse": "500387", "industry": "Cement", "type": "Private"},
    {"name": "Ambuja Cements Ltd", "ticker": "AMBUJACEM", "bse": "500425", "industry": "Cement", "type": "Private"},
    {"name": "ACC Ltd", "ticker": "ACC", "bse": "500410", "industry": "Cement", "type": "Private"},
    {"name": "SBI Life Insurance", "ticker": "SBILIFE", "bse": "540719", "industry": "Life Insurance", "type": "Private"},
    {"name": "HDFC Life Insurance", "ticker": "HDFCLIFE", "bse": "540777", "industry": "Life Insurance", "type": "Private"},
    {"name": "ICICI Prudential Life", "ticker": "ICICIPRULI", "bse": "540133", "industry": "Life Insurance", "type": "Private"},
    {"name": "ICICI Lombard General", "ticker": "ICICIGI", "bse": "540716", "industry": "General Insurance", "type": "Private"},
    {"name": "Zomato Ltd", "ticker": "ZOMATO", "bse": "543320", "industry": "Internet", "type": "Private"},
    {"name": "One97 Communications (Paytm)", "ticker": "PAYTM", "bse": "543396", "industry": "Fintech", "type": "Private"},
    {"name": "IRCTC", "ticker": "IRCTC", "bse": "542830", "industry": "Travel", "type": "Government (PSU)"},
    {"name": "Avenue Supermarts (DMart)", "ticker": "DMART", "bse": "540376", "industry": "Retail", "type": "Private"},
    {"name": "Pidilite Industries", "ticker": "PIDILITIND", "bse": "500331", "industry": "Chemicals", "type": "Private"},
    {"name": "Berger Paints India", "ticker": "BERGEPAINT", "bse": "509480", "industry": "Paints", "type": "Private"},
    {"name": "Havells India Ltd", "ticker": "HAVELLS", "bse": "517354", "industry": "Electricals", "type": "Private"},
    {"name": "Siemens Ltd", "ticker": "SIEMENS", "bse": "500550", "industry": "Capital Goods", "type": "Private"},
    {"name": "ABB India Ltd", "ticker": "ABB", "bse": "500002", "industry": "Capital Goods", "type": "Private"},
    {"name": "BHEL", "ticker": "BHEL", "bse": "500103", "industry": "Capital Goods", "type": "Government (PSU)"},
    {"name": "GAIL (India) Ltd", "ticker": "GAIL", "bse": "532155", "industry": "Gas Transmission", "type": "Government (PSU)"},
    {"name": "Bharat Petroleum Corp Ltd", "ticker": "BPCL", "bse": "500547", "industry": "Oil & Gas", "type": "Government (PSU)"},
    {"name": "Indian Oil Corporation Ltd", "ticker": "IOC", "bse": "530965", "industry": "Oil & Gas", "type": "Government (PSU)"},
    {"name": "Hindustan Petroleum Corp Ltd", "ticker": "HINDPETRO", "bse": "500104", "industry": "Oil & Gas", "type": "Government (PSU)"},
    {"name": "Vedanta Ltd", "ticker": "VEDL", "bse": "500295", "industry": "Metals & Mining", "type": "Private"},
    {"name": "Bharat Electronics Ltd", "ticker": "BEL", "bse": "500049", "industry": "Defence", "type": "Government (PSU)"},
    {"name": "Hindustan Aeronautics", "ticker": "HAL", "bse": "541154", "industry": "Defence", "type": "Government (PSU)"},
    {"name": "Mazagon Dock Shipbuilders", "ticker": "MAZDOCK", "bse": "543237", "industry": "Defence", "type": "Government (PSU)"},
    {"name": "Cochin Shipyard Ltd", "ticker": "COCHINSHIP", "bse": "540678", "industry": "Defence", "type": "Government (PSU)"},
    {"name": "Rail Vikas Nigam Ltd", "ticker": "RVNL", "bse": "542649", "industry": "Railways", "type": "Government (PSU)"},
    {"name": "Indian Railway Finance Corp", "ticker": "IRFC", "bse": "543257", "industry": "Railways", "type": "Government (PSU)"},
    {"name": "Punjab National Bank", "ticker": "PNB", "bse": "532461", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "Bank of Baroda", "ticker": "BANKBARODA", "bse": "532134", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "Canara Bank", "ticker": "CANBK", "bse": "532483", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "Union Bank of India", "ticker": "UNIONBANK", "bse": "532477", "industry": "Public Sector Bank", "type": "Government (PSU)"},
    {"name": "IDBI Bank Ltd", "ticker": "IDBI", "bse": "500116", "industry": "Private Sector Bank", "type": "Government (PSU)"},
    {"name": "Yes Bank Ltd", "ticker": "YESBANK", "bse": "532648", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "IndusInd Bank Ltd", "ticker": "INDUSINDBK", "bse": "532187", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Federal Bank Ltd", "ticker": "FEDERALBNK", "bse": "500469", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "IDFC First Bank", "ticker": "IDFCFIRSTB", "bse": "539437", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Bandhan Bank Ltd", "ticker": "BANDHANBNK", "bse": "541153", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "AU Small Finance Bank", "ticker": "AUBANK", "bse": "540611", "industry": "Private Sector Bank", "type": "Private"},
    {"name": "Cholamandalam Invest", "ticker": "CHOLAFIN", "bse": "511243", "industry": "NBFC", "type": "Private"},
    {"name": "Shriram Finance Ltd", "ticker": "SHRIRAMFIN", "bse": "511218", "industry": "NBFC", "type": "Private"},
    {"name": "Muthoot Finance Ltd", "ticker": "MUTHOOTFIN", "bse": "533398", "industry": "NBFC", "type": "Private"},
    {"name": "LIC Housing Finance", "ticker": "LICHSGFIN", "bse": "500253", "industry": "Housing Finance", "type": "Government (PSU)"},
    {"name": "Power Finance Corp", "ticker": "PFC", "bse": "532810", "industry": "Financial Services", "type": "Government (PSU)"},
    {"name": "REC Ltd", "ticker": "RECLTD", "bse": "532955", "industry": "Financial Services", "type": "Government (PSU)"},
    {"name": "IREDA", "ticker": "IREDA", "bse": "544026", "industry": "Financial Services", "type": "Government (PSU)"},
    {"name": "Jio Financial Services", "ticker": "JIOFIN", "bse": "543940", "industry": "Financial Services", "type": "Private"},
    {"name": "Zydus Lifesciences", "ticker": "ZYDUSLIFE", "bse": "532321", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Lupin Ltd", "ticker": "LUPIN", "bse": "500257", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Tata Power Co Ltd", "ticker": "TATAPOWER", "bse": "500400", "industry": "Power Generation", "type": "Private"},
    {"name": "DLF Ltd", "ticker": "DLF", "bse": "532868", "industry": "Real Estate", "type": "Private"},
    {"name": "Godrej Properties", "ticker": "GODREJPROP", "bse": "533150", "industry": "Real Estate", "type": "Private"},
    {"name": "Trent Ltd", "ticker": "TRENT", "bse": "500251", "industry": "Retail", "type": "Private"},
    {"name": "Info Edge (India)", "ticker": "NAUKRI", "bse": "532777", "industry": "Internet", "type": "Private"},
    {"name": "InterGlobe Aviation", "ticker": "INDIGO", "bse": "539448", "industry": "Aviation", "type": "Private"},
    {"name": "Indraprastha Gas Ltd", "ticker": "IGL", "bse": "532514", "industry": "City Gas", "type": "Government (PSU)"},
    {"name": "Petronet LNG Ltd", "ticker": "PETRONET", "bse": "532522", "industry": "Gas", "type": "Government (PSU)"},
    {"name": "Container Corp of India", "ticker": "CONCOR", "bse": "531344", "industry": "Logistics", "type": "Government (PSU)"},
    {"name": "Torrent Pharmaceuticals", "ticker": "TORNTPHARM", "bse": "500420", "industry": "Pharmaceuticals", "type": "Private"},
    {"name": "Max Healthcare Institute", "ticker": "MAXHEALTH", "bse": "543220", "industry": "Healthcare", "type": "Private"},
    {"name": "Polycab India Ltd", "ticker": "POLYCAB", "bse": "542652", "industry": "Electricals", "type": "Private"},
    {"name": "Bosch Ltd", "ticker": "BOSCHLTD", "bse": "500530", "industry": "Auto Ancillaries", "type": "Private"},
    {"name": "Samvardhana Motherson", "ticker": "MOTHERSON", "bse": "520008", "industry": "Auto Ancillaries", "type": "Private"},
    {"name": "TVS Motor Company", "ticker": "TVSMOTOR", "bse": "532343", "industry": "Automobiles", "type": "Private"},
    {"name": "Cummins India Ltd", "ticker": "CUMMINSIND", "bse": "500480", "industry": "Capital Goods", "type": "Private"},
    {"name": "Page Industries Ltd", "ticker": "PAGEIND", "bse": "533499", "industry": "Textiles", "type": "Private"},
    {"name": "SRF Ltd", "ticker": "SRF", "bse": "503806", "industry": "Chemicals", "type": "Private"},
    {"name": "PI Industries Ltd", "ticker": "PIIND", "bse": "523642", "industry": "Chemicals", "type": "Private"}
]

ANNEXURE_FIELDS = [
    "P/E Ratio", "P/B Ratio", "EPS", "Book Value", 
    "Against 52-week high", "Against 52-week low", "Day change", 
    "Earnings per share", "Price / earnings", "Price / book", 
    "Book value— derived, price ÷ P/B", "Return on equity", 
    "Operating margin", "Net margin", "Jun-26 · Q", "Mar-26 · Q", 
    "FY25-26", "Market Cap", "Size band", "Index membership"
]

def fetch_company_data(comp):
    gf = fetch_google_finance_live_data(comp["ticker"])
    annex = fetch_annexure_all_details(comp["bse"])
    return comp, gf, annex

# --- 4. PERFORMANCE TRACKER STORAGE ---
TRACKER_FILE = "portfolio_tracker.csv"

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        return pd.read_csv(TRACKER_FILE)
    return pd.DataFrame(columns=["Date_Logged", "Ticker", "Entry_Price", "Target_Price"])

def save_picks_to_tracker(top_picks_df):
    tracker = load_tracker()
    new_rows = pd.DataFrame({
        "Date_Logged": [datetime.now().strftime("%Y-%m-%d")] * len(top_picks_df),
        "Ticker": top_picks_df["Ticker"].values,
        "Entry_Price": top_picks_df["_price"].values,
        "Target_Price": top_picks_df["_price"].values * 1.10
    })
    
    # Avoid duplicates logged on the same day
    tracker = pd.concat([tracker, new_rows], ignore_index=True)
    tracker.drop_duplicates(subset=["Date_Logged", "Ticker"], keep="first", inplace=True)
    tracker.to_csv(TRACKER_FILE, index=False)

# --- 5. MAIN EXECUTION ---
with st.spinner("Fetching data for 100+ companies (running in parallel for speed)..."):
    table_rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_company_data, COMPANIES))

    for comp, gf, annex in results:
        row = {
            "Company Name": comp["name"],
            "Ticker": comp["ticker"],
            "Current Price (Google Finance)": gf["price_str"],
            "Absolute Change (Google Finance)": gf["abs_change_str"],
            "Change % (Google Finance)": gf["pct_change_str"]
        }
        for field in ANNEXURE_FIELDS:
            row[f"{field} (TheAnnexure)"] = annex.get(field, "N/A")
        row["Industry"] = comp["industry"]
        row["Company Type"] = comp["type"]
        table_rows.append(row)

df_display = pd.DataFrame(table_rows)

# Create Tabs
tab1, tab2 = st.tabs(["🎯 Live Scanner & 10% Engine", "📈 Performance Tracker"])

with tab1:
    st.markdown("### 🎯 Top Picks for ~10% Return (1-2 Months)")
    st.markdown("Calculated by analyzing **Book Value Support**, **52-week high recovery potential**, **valuation (P/E)**, and **ROE**.")

    def parse_percentage(val_str):
        if not isinstance(val_str, str) or val_str == "N/A": return 0.0
        try: return float(val_str.replace('%', '').replace(',', '').strip())
        except: return 0.0

    def parse_float(val_str):
        if not isinstance(val_str, str) or val_str == "N/A": return 0.0
        try: return float(re.sub(r'[^\d.-]', '', val_str))
        except: return 0.0

    df_display['_price'] = df_display['Current Price (Google Finance)'].apply(parse_float)
    df_display['_pe'] = df_display['P/E Ratio (TheAnnexure)'].apply(parse_float)
    df_display['_pb'] = df_display['P/B Ratio (TheAnnexure)'].apply(parse_float)
    df_display['_roe'] = df_display['Return on equity (TheAnnexure)'].apply(parse_float)
    df_display['_down_52w'] = df_display['Against 52-week high (TheAnnexure)'].apply(parse_percentage)

    candidates = df_display[(df_display['_price'] > 0) & (df_display['_down_52w'] < -5)].copy()

    def calculate_10pct_score(row):
        score = 0
        reasons = []
        if 0 < row['_pb'] < 1.0:
            score += 4
            reasons.append("Below Book Value (P/B < 1)")
        elif 1.0 <= row['_pb'] < 1.5:
            score += 2
            reasons.append("Attractive P/B")
        if 0 < row['_pe'] < 20:
            score += 2
            reasons.append("Low P/E")
        if row['_down_52w'] < -15: 
            score += 3
            reasons.append("Deep pullback from high")
        if row['_roe'] > 15:
            score += 3
            reasons.append("Strong ROE")
        return pd.Series([score, " | ".join(reasons)])

    if not candidates.empty:
        candidates[['_score', '_reason']] = candidates.apply(calculate_10pct_score, axis=1)
        top_picks = candidates.sort_values(by='_score', ascending=False).head(3)
        
        cols = st.columns(3)
        for idx, (index, row) in enumerate(top_picks.iterrows()):
            target_price = row['_price'] * 1.10
            with cols[idx]:
                st.metric(
                    label=f"🏆 {row['Ticker']} ({row['Industry']})",
                    value=f"Target: ₹{target_price:.2f}",
                    delta=f"Current: ₹{row['_price']:.2f}"
                )
                st.caption(f"**Why?** {row['_reason']}")
                st.caption(f"**Book Value:** {row['Book Value (TheAnnexure)']} | **P/B:** {row['P/B Ratio (TheAnnexure)']}")
                st.caption(f"52W High: {row['Against 52-week high (TheAnnexure)']} | ROE: {row['Return on equity (TheAnnexure)']}")
        
        # Save Button
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save Top 3 Picks to Tracker"):
            save_picks_to_tracker(top_picks)
            st.success("Picks saved locally! Download the updated file below and push it to your GitHub repo.")
    else:
        st.info("No strong 10% candidates found meeting the criteria right now.")

    df_display_clean = df_display.drop(columns=['_price', '_pe', '_pb', '_roe', '_down_52w'])

    st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
    st.markdown("### 📋 Full Institutional Data Matrix")
    st.dataframe(
        df_display_clean,
        use_container_width=True,
        hide_index=True,
        height=min(750, 45 + 35 * len(df_display_clean)) 
    )

with tab2:
    st.markdown("### 📈 Performance Tracker")
    st.markdown("Track your saved picks to see if they have achieved the 10% goal.")
    
    tracker_df = load_tracker()
    
    if tracker_df.empty:
        st.info("No picks saved yet. Go to the 'Live Scanner' tab and save your top picks!")
    else:
        # Calculate live performance for tracked picks
        st.markdown("Fetching live prices for your tracked portfolio...")
        
        results = []
        for index, row in tracker_df.iterrows():
            ticker = row["Ticker"]
            entry_price = row["Entry_Price"]
            target_price = row["Target_Price"]
            date_logged = row["Date_Logged"]
            
            # Fetch current price
            live_data = fetch_google_finance_live_data(ticker)
            current_price = live_data["price_val"]
            
            if current_price > 0:
                current_return = ((current_price - entry_price) / entry_price) * 100
                days_elapsed = (datetime.now() - datetime.strptime(date_logged, "%Y-%m-%d")).days
                
                if current_price >= target_price:
                    status = "✅ Goal Achieved!"
                else:
                    status = "⏳ In Progress"
                    
                results.append({
                    "Date Logged": date_logged,
                    "Ticker": ticker,
                    "Entry Price": f"₹{entry_price:.2f}",
                    "Target Price": f"₹{target_price:.2f}",
                    "Current Price": f"₹{current_price:.2f}",
                    "Return %": f"{current_return:+.2f}%",
                    "Days Active": days_elapsed,
                    "Status": status
                })
            else:
                results.append({
                    "Date Logged": date_logged,
                    "Ticker": ticker,
                    "Entry Price": f"₹{entry_price:.2f}",
                    "Target Price": f"₹{target_price:.2f}",
                    "Current Price": "N/A",
                    "Return %": "N/A",
                    "Days Active": (datetime.now() - datetime.strptime(date_logged, "%Y-%m-%d")).days,
                    "Status": "⚠️ Data Missing"
                })
                
        if results:
            tracker_display_df = pd.DataFrame(results)
            
            # Apply styling
            def color_status(val):
                if "Achieved" in val: return 'color: #34D399; font-weight: bold;'
                elif "Progress" in val: return 'color: #C6992F;'
                return ''
                
            styled_tracker = tracker_display_df.style.map(color_status, subset=["Status"])
            
            st.dataframe(
                styled_tracker,
                use_container_width=True,
                hide_index=True
            )
            
        # Download Button for GitHub persistence
        st.markdown("<br>", unsafe_allow_html=True)
        with open(TRACKER_FILE, "rb") as file:
            st.download_button(
                label="📥 Download portfolio_tracker.csv (Push to GitHub)",
                data=file,
                file_name="portfolio_tracker.csv",
                mime="text/csv"
            )

# Refresh Button (Global)
st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
if st.button("🔄 Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()
