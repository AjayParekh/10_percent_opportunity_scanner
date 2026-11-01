import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time

# -------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -------------------------------------------------------------------
st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("📈 Reliance Industries Ltd - Dashboard")
st.write("Data sourced strictly from TheAnnexure.")

# -------------------------------------------------------------------
# 2. THEANNEXURE SCRAPER (Bulletproof Regex Version)
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_annexure_data():
    url = "https://theannexure.com/company/500325.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        time.sleep(1) # Be respectful to the server
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect to TheAnnexure: {e}"

    # Get the raw text of the entire page
    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    
    # Initialize all metrics to N/A (strict adherence to rules)
    metrics = {
        "Market Cap": "N/A",
        "P/E Ratio": "N/A",
        "P/B Ratio": "N/A",
        "EPS": "N/A",
        "Book Value": "N/A",
        "ROE": "N/A",
        "Operating Margin": "N/A",
        "Net Margin": "N/A",
        "Debt to Equity": "N/A",
        "Current Price": "N/A"
    }

    # --- REGEX EXTRACTION ---
    # 1. Top Summary Cards
    mc_match = re.search(r"Market cap ₹([\d,\.]+) cr", text)
    if mc_match:
        metrics["Market Cap"] = f"₹{mc_match.group(1)} Cr"
        
    pe_pb_match = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
    if pe_pb_match:
        metrics["P/E Ratio"] = f"{pe_pb_match.group(1)}×"
        metrics["P/B Ratio"] = f"{pe_pb_match.group(2)}×"
        
    eps_match = re.search(r"EPS ₹([\d\.]+)", text)
    if eps_match:
        metrics["EPS"] = f"₹{eps_match.group(1)}"
        
    bv_match = re.search(r"BV ₹([\d\.]+)", text)
    if bv_match:
        metrics["Book Value"] = f"₹{bv_match.group(1)}"
        
    # Assuming TheAnnexure shows current price somewhere similar to this:
    price_match = re.search(r"Current Price ₹([\d,\.]+)", text)
    if price_match:
        metrics["Current Price"] = f"₹{price_match.group(1)}"

    # 2. Ratio Tables (Looking for the exact text patterns)
    roe_match = re.search(r"Return on equity \| ([\d\.]+%)", text)
    if roe_match:
        metrics["ROE"] = roe_match.group(1)
        
    op_margin_match = re.search(r"Operating margin \| ([\d\.]+%)", text)
    if op_margin_match:
        metrics["Operating Margin"] = op_margin_match.group(1)
        
    net_margin_match = re.search(r"Net margin \| ([\d\.]+%)", text)
    if net_margin_match:
        metrics["Net Margin"] = net_margin_match.group(1)
        
    # Debt to Equity often appears as "Debt to Equity (x) 0.42" or similar in the table text
    debt_match = re.search(r"Debt to Equity \(x\) ([\d\.]+)", text)
    if debt_match:
        metrics["Debt to Equity"] = debt_match.group(1)

    return metrics, "Success"

# -------------------------------------------------------------------
# 3. MAIN APP LAYOUT
# -------------------------------------------------------------------
with st.spinner("Fetching data from TheAnnexure..."):
    data, message = fetch_annexure_data()

if data is None:
    st.error(message)
else:
    st.success("Successfully fetched data from TheAnnexure.")
    
    # --- Display Valuation ---
    st.subheader("Valuation Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Cap", data["Market Cap"])
    col2.metric("P/E Ratio", data["P/E Ratio"])
    col3.metric("P/B Ratio", data["P/B Ratio"])
    col4.metric("Debt to Equity", data["Debt to Equity"])
    
    st.divider()
    
    # --- Display Profitability ---
    st.subheader("Profitability & Returns")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Return on Equity (ROE)", data["ROE"])
    col6.metric("Operating Margin", data["Operating Margin"])
    col7.metric("Net Margin", data["Net Margin"])
    col8.metric("EPS", data["EPS"])
    
    st.divider()
    
    # --- Display Per Share ---
    st.subheader("Per Share Data")
    col9, col10 = st.columns(2)
    col9.metric("Book Value per Share", data["Book Value"])
    
    # Refresh Button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
