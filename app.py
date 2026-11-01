import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("📈 Reliance Industries Ltd - Opportunity Dashboard")

# -------------------------------------------------------------------
# 1. THEANNEXURE FUNDAMENTALS
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_annexure_data():
    url = "https://theannexure.com/company/500325.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"TheAnnexure Error: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    page_text = soup.get_text(separator=' ', strip=True)
    
    metrics = {
        "Market Cap": "N/A", "P/E Ratio": "N/A", "P/B Ratio": "N/A",
        "EPS": "N/A", "Book Value": "N/A", "ROE": "N/A",
        "Operating Margin": "N/A", "Net Margin": "N/A", "Debt to Equity": "N/A"
    }

    mc = re.search(r"Market cap ₹([\d,\.]+) cr", page_text)
    if mc: metrics["Market Cap"] = f"₹{mc.group(1)} Cr"
    pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", page_text)
    if pe_pb:
        metrics["P/E Ratio"] = f"{pe_pb.group(1)}×"
        metrics["P/B Ratio"] = f"{pe_pb.group(2)}×"
    eps = re.search(r"EPS ₹([\d\.]+)", page_text)
    if eps: metrics["EPS"] = f"₹{eps.group(1)}"
    bv = re.search(r"BV ₹([\d\.]+)", page_text)
    if bv: metrics["Book Value"] = f"₹{bv.group(1)}"

    # Parse table rows for ratio metrics
    for row in soup.find_all('tr'):
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            val = cells[1].get_text(strip=True)
            
            if "return on equity" in label: metrics["ROE"] = val
            elif "operating margin" in label: metrics["Operating Margin"] = val
            elif "net margin" in label: metrics["Net Margin"] = val
            elif "debt to equity" in label: # Captures "Debt to Equity (x)"
                metrics["Debt to Equity"] = val

    return metrics, "Success"

# -------------------------------------------------------------------
# 2. GOOGLE FINANCE LIVE PRICE
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=300) # Cache for 5 minutes
def fetch_google_finance_data():
    url = "https://www.google.com/finance/quote/RELIANCE:NSE"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Google Finance Error: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    
    live_data = {"Price": "N/A", "Change": "N/A", "Change %": "N/A"}
    
    # Google Finance uses divs with class "YMlKec fxKbKc" for price
    price_div = soup.find('div', class_='YMlKec fxKbKc')
    if price_div:
        live_data["Price"] = price_div.get_text(strip=True)
    
    # Extracting change and percentage change is trickier; we parse the text
    # Look for the parent div containing price info
    price_parent = price_div.find_parent('div') if price_div else None
    if price_parent:
        full_text = price_parent.get_text(separator=' ', strip=True)
        # Example: "₹1,170.90 -0.60% (-7.10)"
        # We use regex to find the percentage and absolute change
        change_match = re.search(r'([-+]?\d+\.\d+)%\s*\(([-+]?\d+\.\d+)\)', full_text)
        if change_match:
            live_data["Change %"] = f"{change_match.group(1)}%"
            live_data["Change"] = change_match.group(2)

    return live_data, "Success"

# -------------------------------------------------------------------
# 3. MONEYCONTROL TECHNICALS (Fallback)
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_moneycontrol_data():
    url = "https://www.moneycontrol.com/technical-analysis/relianceindustries/ri/daily"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        time.sleep(1.5)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Moneycontrol Error: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    tech = {"RSI (14)": "N/A", "50-Day SMA": "N/A", "MACD": "N/A"}

    rsi_match = re.search(r"RSI\(14\)\s*\|\s*([\d\.]+)", text)
    if rsi_match: tech["RSI (14)"] = rsi_match.group(1)

    sma50_match = re.search(r"50\s*\|\s*([\d,\.]+)", text)
    if sma50_match: tech["50-Day SMA"] = f"₹{sma50_match.group(1)}"

    macd_match = re.search(r"MACD\(12,26,9\)\s*\|\s*(-?[\d\.]+)", text)
    if macd_match: tech["MACD"] = macd_match.group(1)

    return tech, "Success"

# -------------------------------------------------------------------
# 4. MAIN APP LAYOUT
# -------------------------------------------------------------------
st.subheader("💰 Live Market Price (Source: Google Finance)")
gf_data, gf_msg = fetch_google_finance_data()
if gf_data:
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Market Price", gf_data["Price"])
    col2.metric("Change", gf_data["Change"])
    col3.metric("Change %", gf_data["Change %"])
else:
    st.warning(f"Could not load live price: {gf_msg}")

st.divider()

st.subheader("📊 Fundamental Metrics (Source: TheAnnexure)")
fund_data, fund_msg = fetch_annexure_data()
if fund_data:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market Cap", fund_data["Market Cap"])
    c2.metric("P/E Ratio", fund_data["P/E Ratio"])
    c3.metric("Debt to Equity", fund_data["Debt to Equity"]) # Should now populate
    c4.metric("ROE", fund_data["ROE"])
    
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Operating Margin", fund_data["Operating Margin"])
    c6.metric("Net Margin", fund_data["Net Margin"])
    c7.metric("EPS", fund_data["EPS"])
    c8.metric("Book Value", fund_data["Book Value"])
else:
    st.warning(f"Could not load fundamentals: {fund_msg}")

st.divider()

st.subheader("📈 Technical Entry Metrics (Source: Moneycontrol)")
tech_data, tech_msg = fetch_moneycontrol_data()
if tech_data:
    c9, c10, c11 = st.columns(3)
    c9.metric("RSI (14)", tech_data["RSI (14)"])
    c10.metric("50-Day SMA", tech_data["50-Day SMA"])
    c11.metric("MACD", tech_data["MACD"])
else:
    st.warning(f"Could not load technical metrics: {tech_msg}")
