import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -------------------------------------------------------------------
st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("📈 Reliance Industries Ltd - Opportunity Dashboard")
st.write("Data sourced directly from TheAnnexure and Moneycontrol.")

# -------------------------------------------------------------------
# 2. SCRAPING FUNCTIONS
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_annexure_data():
    url = "https://theannexure.com/company/500325.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        time.sleep(1)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect to TheAnnexure: {e}"

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

    # Scan all tables for ratio rows (ROE, Margins, Debt/Equity)
    for row in soup.find_all('tr'):
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            val = cells[1].get_text(strip=True)
            
            if "return on equity" in label: metrics["ROE"] = val
            elif "operating margin" in label: metrics["Operating Margin"] = val
            elif "net margin" in label: metrics["Net Margin"] = val
            elif "debt to equity" in label or "debt/equity" in label:
                metrics["Debt to Equity"] = val

    return metrics, "Success"

@st.cache_data(show_spinner=False, ttl=3600)
def fetch_moneycontrol_data():
    url = "https://www.moneycontrol.com/technical-analysis/relianceindustries/ri/daily"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        time.sleep(1.5)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect to Moneycontrol: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)

    tech = {"Current Price": "N/A", "RSI (14)": "N/A", "50-Day SMA": "N/A", "MACD": "N/A"}

    price_match = re.search(r"As on.*?([\d,]+\.\d+)", text)
    if price_match: tech["Current Price"] = f"₹{price_match.group(1)}"

    rsi_match = re.search(r"RSI\(14\)\s*\|\s*([\d\.]+)", text)
    if rsi_match: tech["RSI (14)"] = rsi_match.group(1)

    sma50_match = re.search(r"50\s*\|\s*([\d,\.]+)", text)
    if sma50_match: tech["50-Day SMA"] = f"₹{sma50_match.group(1)}"

    macd_match = re.search(r"MACD\(12,26,9\)\s*\|\s*(-?[\d\.]+)", text)
    if macd_match: tech["MACD"] = macd_match.group(1)

    return tech, "Success"

# -------------------------------------------------------------------
# 3. MAIN APP LAYOUT
# -------------------------------------------------------------------
with st.spinner("Fetching fundamental data from TheAnnexure..."):
    fund_data, fund_msg = fetch_annexure_data()

with st.spinner("Fetching technical data from Moneycontrol..."):
    tech_data, tech_msg = fetch_moneycontrol_data()

if fund_data:
    st.subheader("📊 Fundamental Metrics (Source: TheAnnexure)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Cap", fund_data["Market Cap"])
    col2.metric("P/E Ratio", fund_data["P/E Ratio"])
    col3.metric("Debt to Equity", fund_data["Debt to Equity"])
    col4.metric("ROE", fund_data["ROE"])
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Operating Margin", fund_data["Operating Margin"])
    col6.metric("Net Margin", fund_data["Net Margin"])
    col7.metric("EPS", fund_data["EPS"])
    col8.metric("Book Value", fund_data["Book Value"])

    st.divider()

if tech_data:
    st.subheader("📈 Technical Entry Metrics (Source: Moneycontrol)")
    col9, col10, col11, col12 = st.columns(4)
    col9.metric("Current Market Price", tech_data["Current Price"])
    col10.metric("RSI (14)", tech_data["RSI (14)"])
    col11.metric("50-Day SMA", tech_data["50-Day SMA"])
    col12.metric("MACD", tech_data["MACD"])
else:
    st.warning(f"Could not load technical metrics: {tech_msg}")

st.sidebar.markdown("### Data Quality & Sources")
st.sidebar.info("Fundamental data is strictly sourced from TheAnnexure. Technical data is sourced from Moneycontrol. Missing values are not estimated.")
