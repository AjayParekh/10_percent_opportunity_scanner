import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

# --- 1. PAGE SETUP & UI LAYER (From your reference code) ---
st.set_page_config(page_title="Reliance - 10% Opportunity Scanner", layout="wide", page_icon="🏛️")

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
        line-height: 1.15;
    }
    .omc-subtitle {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.95rem;
        color: var(--text-secondary);
        max-width: 720px;
        margin-bottom: 1.1rem;
    }

    div[data-testid="stMetric"] {
        background-color: var(--bg-panel);
        border: 1px solid var(--border-hairline);
        border-radius: 3px;
        padding: 0.9rem 1rem 0.7rem 1rem;
    }
    div[data-testid="stMetric"] label {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.7rem !important;
        letter-spacing: 0.06em;
        color: var(--text-secondary) !important;
        text-transform: uppercase;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        font-size: 1.35rem !important;
    }
    div[data-testid="stMetricDelta"] {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    hr { border-color: var(--border-hairline) !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. EXACT GOOGLE FINANCE SCRAPER (With the Absolute Change Fallback) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def robust_numeric_parse(val_str):
    if not val_str or pd.isna(val_str):
        return 0.0
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val_str).replace(',', '').strip())
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

@st.cache_data(ttl=300)
def fetch_google_finance_live_data():
    url = "https://www.google.com/finance/beta/quote/RELIANCE:NSE?tab=financials"
    metrics = {
        "price_str": "N/A", "price_val": 0.0, "pct_change_str": "N/A", "abs_change_str": "N/A"
    }
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return metrics
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
            # FALLBACK LOGIC FROM YOUR REFERENCE CODE
            change_text = ""
            if price_el:
                parent = price_el.find_parent()
                if parent:
                    sibling_divs = parent.find_all(string=re.compile(r'%'))
                    if sibling_divs:
                        change_text = sibling_divs[0].strip()
            if change_text:
                clean_text = change_text.replace("Today", "").replace("After hours", "").strip()
                extracted_metrics = re.findall(r'([+-]?\d+(?:\.\d+)?%?)', clean_text)
                if extracted_metrics:
                    metrics["pct_change_str"] = extracted_metrics[0]
            
            # Mathematical calculation for Absolute Change
            try:
                if metrics["price_val"] > 0 and metrics["pct_change_str"] != "N/A":
                    raw_pct = float(re.sub(r'[^\d.-]', '', metrics["pct_change_str"]))
                    prev_close = metrics["price_val"] / (1 + (raw_pct / 100.0))
                    calculated_abs_change = metrics["price_val"] - prev_close
                    metrics["abs_change_str"] = f"{'+' if calculated_abs_change > 0 else ''}{calculated_abs_change:.2f}"
            except Exception:
                pass
                
    except Exception as e:
        pass
        
    return metrics


# --- 3. THEANNEXURE SCRAPER (Fixed Debt to Equity) ---
@st.cache_data(ttl=3600)
def fetch_annexure_fundamentals():
    url = "https://theannexure.com/company/500325.html"
    metrics = {
        "Market Cap": "N/A", "P/E Ratio": "N/A", "P/B Ratio": "N/A",
        "EPS": "N/A", "Book Value": "N/A", "ROE": "N/A",
        "Operating Margin": "N/A", "Net Margin": "N/A", "Debt to Equity": "N/A"
    }
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        # Top Summary
        mc = re.search(r"Market cap ₹([\d,\.]+) cr", text)
        if mc: metrics["Market Cap"] = f"₹{mc.group(1)} Cr"
        
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            metrics["P/E Ratio"] = f"{pe_pb.group(1)}×"
            metrics["P/B Ratio"] = f"{pe_pb.group(2)}×"
            
        eps = re.search(r"EPS ₹([\d\.]+)", text)
        if eps: metrics["EPS"] = f"₹{eps.group(1)}"
        
        bv = re.search(r"BV ₹([\d\.]+)", text)
        if bv: metrics["Book Value"] = f"₹{bv.group(1)}"

        # Tables (ROE, Margins, Debt/Equity) - Checking BOTH th and td
        for row in soup.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                label = re.sub(r'\s+', ' ', cells[0].get_text(strip=True).lower())
                val = cells[1].get_text(strip=True)
                
                if "return on equity" in label: metrics["ROE"] = val
                elif "operating margin" in label: metrics["Operating Margin"] = val
                elif "net margin" in label: metrics["Net Margin"] = val
                elif "debt to equity" in label: 
                    metrics["Debt to Equity"] = val
                    
    except Exception as e:
        pass
        
    return metrics


# --- 4. MAIN APP LAYOUT ---
st.markdown(
    """
    <div class="omc-eyebrow">Institutional Coverage · Energy</div>
    <div class="omc-title">🏛️ Reliance Industries Ltd</div>
    <div class="omc-subtitle">Production-ready quantitative screening & valuation matrices for Reliance.</div>
    """,
    unsafe_allow_html=True
)

# Fetch Data
with st.spinner("Fetching live data..."):
    live_data = fetch_google_finance_live_data()
    fund_data = fetch_annexure_fundamentals()

# Display Google Finance Live Data
st.markdown('<div class="omc-eyebrow" style="margin-top:1rem;">Live Market Price · Google Finance</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
col1.metric("Current Market Price", live_data["price_str"])
col2.metric("Absolute Change", live_data["abs_change_str"])
col3.metric("Change %", live_data["pct_change_str"])

st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)

# Display TheAnnexure Fundamentals
st.markdown('<div class="omc-eyebrow">Fundamental Metrics · TheAnnexure</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Market Cap", fund_data["Market Cap"])
c2.metric("P/E Ratio", fund_data["P/E Ratio"])
c3.metric("Debt to Equity", fund_data["Debt to Equity"])
c4.metric("ROE", fund_data["ROE"])

c5, c6, c7, c8 = st.columns(4)
c5.metric("Operating Margin", fund_data["Operating Margin"])
c6.metric("Net Margin", fund_data["Net Margin"])
c7.metric("EPS", fund_data["EPS"])
c8.metric("Book Value", fund_data["Book Value"])

# Refresh button
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
