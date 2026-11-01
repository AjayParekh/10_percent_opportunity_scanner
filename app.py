import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -------------------------------------------------------------------
st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("📈 Reliance Industries Ltd - Financial Dashboard")
st.write("Automated extraction of fundamental data from TheAnnexure.")

# -------------------------------------------------------------------
# 2. SCRAPING FUNCTION
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600) # Cache for 1 hour
def fetch_reliance_data():
    # URL for Reliance (BSE Code: 500325)
    url = "https://theannexure.com/company/500325.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        time.sleep(1) # Respectful delay
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect to TheAnnexure: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # --- A. Extract Summary Metrics using Regex ---
    metrics = {
        "Market Cap": "N/A",
        "P/E Ratio": "N/A",
        "P/B Ratio": "N/A",
        "EPS": "N/A",
        "Book Value": "N/A",
        "ROE": "N/A",
        "Operating Margin": "N/A",
        "Net Margin": "N/A",
        "Debt to Equity": "N/A"
    }
    
    # We get the whole text to search for the summary block
    text = soup.get_text(separator=' ', strip=True)
    
    # Market Cap
    mc_match = re.search(r"Market cap ₹([\d,\.]+) cr", text)
    if mc_match:
        metrics["Market Cap"] = f"₹{mc_match.group(1)} Cr"
        
    # P/E and P/B
    pe_match = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
    if pe_match:
        metrics["P/E Ratio"] = f"{pe_match.group(1)}×"
        metrics["P/B Ratio"] = f"{pe_match.group(2)}×"
        
    # EPS and Book Value
    eps_match = re.search(r"EPS ₹([\d\.]+)", text)
    if eps_match:
        metrics["EPS"] = f"₹{eps_match.group(1)}"
        
    bv_match = re.search(r"BV ₹([\d\.]+)", text)
    if bv_match:
        metrics["Book Value"] = f"₹{bv_match.group(1)}"

    # --- B. Extract Table Metrics using BeautifulSoup ---
    # TheAnnexure uses tables for ratios like ROE, Margins, Debt/Equity
    rows = soup.find_all('tr')
    for row in rows:
        th = row.find('th')
        td = row.find('td')
        if th and td:
            label = th.text.strip().lower()
            value = td.text.strip()
            
            if "return on equity" in label:
                metrics["ROE"] = value
            elif "operating margin" in label:
                metrics["Operating Margin"] = value
            elif "net margin" in label:
                metrics["Net Margin"] = value
            elif "debt to equity" in label or "debt/equity" in label:
                metrics["Debt to Equity"] = value

    return metrics, "Success"

# -------------------------------------------------------------------
# 3. MAIN APP LAYOUT
# -------------------------------------------------------------------
with st.spinner("Fetching Reliance data from TheAnnexure..."):
    data, message = fetch_reliance_data()

if data is None:
    st.error(message)
    st.info("The website might be temporarily down or the layout changed.")
else:
    st.success("Successfully fetched latest data!")
    
    # --- Row 1: Valuation ---
    st.subheader("Valuation Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Cap", data["Market Cap"])
    col2.metric("P/E Ratio", data["P/E Ratio"])
    col3.metric("P/B Ratio", data["P/B Ratio"])
    col4.metric("Debt to Equity", data["Debt to Equity"])
    
    st.divider()
    
    # --- Row 2: Profitability & Returns ---
    st.subheader("Profitability & Returns")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Return on Equity (ROE)", data["ROE"])
    col6.metric("Operating Margin", data["Operating Margin"])
    col7.metric("Net Margin", data["Net Margin"])
    col8.metric("EPS", data["EPS"])
    
    st.divider()
    
    # --- Row 3: Book Value ---
    st.subheader("Per Share Data")
    col9, col10 = st.columns(2)
    col9.metric("Book Value per Share", data["Book Value"])

    # Optional: Add a button to refresh the cache
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.sidebar.markdown("### Data Source")
st.sidebar.info("Data is sourced directly from [TheAnnexure](https://theannexure.com/). No missing data is replaced with estimates.")
