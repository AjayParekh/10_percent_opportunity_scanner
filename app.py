import streamlit as st
from scrapers.annexure_scraper import scrape_reliance_fundamentals
from scrapers.moneycontrol_scraper import scrape_moneycontrol_technicals

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("📈 Reliance Industries Ltd - Opportunity Dashboard")

# 1. Fetch Data
with st.spinner("Fetching fundamental data from TheAnnexure..."):
    fund_data, fund_msg = scrape_reliance_fundamentals()

with st.spinner("Fetching technical data from Moneycontrol..."):
    tech_data, tech_msg = scrape_moneycontrol_technicals()

# 2. Display Fundamental Metrics
if fund_data:
    st.subheader("📊 Fundamental Metrics (Source: TheAnnexure)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Cap", fund_data["Market Cap"])
    col2.metric("P/E Ratio", fund_data["P/E Ratio"])
    col3.metric("Debt to Equity", fund_data["Debt to Equity"]) # Now populated
    col4.metric("ROE", fund_data["ROE"])
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Operating Margin", fund_data["Operating Margin"])
    col6.metric("Net Margin", fund_data["Net Margin"])
    col7.metric("EPS", fund_data["EPS"])
    col8.metric("Book Value", fund_data["Book Value"])

    st.divider()

# 3. Display Technical Metrics
if tech_data:
    st.subheader("📈 Technical Entry Metrics (Source: Moneycontrol)")
    col9, col10, col11, col12 = st.columns(4)
    col9.metric("Current Market Price", tech_data["Current Price"])
    col10.metric("RSI (14)", tech_data["RSI (14)"])
    col11.metric("50-Day SMA", tech_data["50-Day SMA"])
    col12.metric("MACD", tech_data["MACD"])

else:
    st.warning(f"Could not load technical metrics: {tech_msg}")
