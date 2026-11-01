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
st.title("📈 Reliance Industries Ltd - Full Data Extract")
st.write("Fetching all available fundamental data strictly from TheAnnexure.")

# -------------------------------------------------------------------
# 2. COMPREHENSIVE SCRAPING FUNCTION
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def fetch_all_reliance_data():
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
    text = soup.get_text(separator=' ', strip=True)
    
    # --- A. Extract Top Summary Cards ---
    summary_data = {}
    
    mc_match = re.search(r"Market cap ₹([\d,\.]+) cr", text)
    if mc_match: summary_data["Market Cap"] = f"₹{mc_match.group(1)} Cr"
        
    pe_pb_match = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
    if pe_pb_match:
        summary_data["P/E Ratio"] = f"{pe_pb_match.group(1)}×"
        summary_data["P/B Ratio"] = f"{pe_pb_match.group(2)}×"
        
    eps_match = re.search(r"EPS ₹([\d\.]+)", text)
    if eps_match: summary_data["EPS"] = f"₹{eps_match.group(1)}"
        
    bv_match = re.search(r"BV ₹([\d\.]+)", text)
    if bv_match: summary_data["Book Value"] = f"₹{bv_match.group(1)}"

    # --- B. Extract ALL Data from Tables ---
    # We will loop through every row in every table.
    # The first cell is usually the metric name, the second is the value.
    table_data = {}
    
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            
            # We need at least 2 columns (Label and at least one value)
            if len(cells) >= 2:
                # Clean the label (first column)
                label = cells[0].get_text(separator=' ', strip=True)
                
                # Clean the value (second column - we assume this is the latest year)
                value = cells[1].get_text(separator=' ', strip=True)
                
                # Ignore empty rows or header rows
                if label and value and label.lower() not in ["metric", "ratio", "particulars"]:
                    # If the metric is already in our summary, we skip to avoid duplicates
                    if label not in summary_data:
                        table_data[label] = value

    return summary_data, table_data, "Success"

# -------------------------------------------------------------------
# 3. MAIN APP LAYOUT
# -------------------------------------------------------------------
with st.spinner("Extracting all data from TheAnnexure..."):
    summary, table_details, message = fetch_all_reliance_data()

if summary is None:
    st.error(message)
else:
    st.success("Successfully extracted all data!")
    
    # --- Display Top Summary ---
    st.subheader("1. Top Summary Cards")
    cols = st.columns(4)
    keys = list(summary.keys())
    
    for i, key in enumerate(keys):
        cols[i % 4].metric(key, summary[key])

    st.divider()
    
    # --- Display All Table Data ---
    st.subheader("2. Detailed Metrics from Tables")
    st.write("Below is every metric found in the tables on TheAnnexure. Review this list and let me know which ones you want to use for the 10% Opportunity Score.")
    
    if table_details:
        # Convert the dictionary to a DataFrame for a beautiful display
        df = pd.DataFrame(list(table_details.items()), columns=["Metric Name", "Current Value"])
        
        # Display as a dataframe
        st.dataframe(df, use_container_width=True, height=600)
        
        # Provide a CSV download so you can review it offline
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Full Data Extract as CSV",
            data=csv,
            file_name='reliance_full_data.csv',
            mime='text/csv',
        )
    else:
        st.warning("No table data could be extracted.")

    # Refresh Button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
