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
st.title("10% Opportunity Scanner")
st.write("Automated extraction from TheAnnexure.")

# -------------------------------------------------------------------
# 2. SCRAPING FUNCTIONS
# -------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def scrape_company_list():
    """Fetches the full list of companies from TheAnnexure."""
    url = "https://theannexure.com/companies.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        time.sleep(1)  # Respectful delay
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')
    if not table:
        return None, "Could not find the company table."

    rows = table.find_all('tr')
    headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
    
    data = []
    for row in rows[1:]:
        cols = [td.text.strip() for td in row.find_all('td')]
        if len(cols) == len(headers):
            data.append(cols)

    df = pd.DataFrame(data, columns=headers)
    return df, "Success"

@st.cache_data(show_spinner=False)
def scrape_reliance_metrics():
    """Scrapes key metrics from Reliance's specific page."""
    url = "https://theannexure.com/company/500325.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        time.sleep(1)  # Respectful delay
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to connect to Reliance page: {e}"

    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)

    # Regex patterns to extract data from the text
    patterns = {
        "Market Cap": r"Market cap ₹([\d,\.]+) cr",
        "P/E Ratio": r"P/E · P/B [\d\.]+× · [\d\.]+×",
        "EPS": r"EPS ₹([\d\.]+)",
        "Book Value": r"BV ₹([\d\.]+)",
        "ROE": r"Return on equity \| ([\d\.]+%)",
        "Operating Margin": r"Operating margin \| ([\d\.]+%)",
        "Net Margin": r"Net margin \| ([\d\.]+%)"
    }

    metrics = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            if key == "P/E Ratio":
                # Extract the first number (P/E)
                pe_match = re.search(r"P/E · P/B ([\d\.]+)×", text)
                metrics[key] = f"{pe_match.group(1)}×" if pe_match else "N/A"
            else:
                metrics[key] = match.group(1)
        else:
            metrics[key] = "N/A"

    return metrics, "Success"

# -------------------------------------------------------------------
# 3. MAIN APP LAYOUT
# -------------------------------------------------------------------
# --- Fetch Data ---
with st.spinner("Fetching company list and Reliance data..."):
    company_df, list_message = scrape_company_list()
    reliance_metrics, reliance_message = scrape_reliance_metrics()

# --- Display Reliance Metrics (Top Section) ---
st.subheader("📊 Reliance Industries Ltd - Key Metrics")

if reliance_metrics:
    # Create a 4-column layout for the metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Cap", f"₹{reliance_metrics.get('Market Cap', 'N/A')} Cr")
    col2.metric("P/E Ratio", reliance_metrics.get("P/E Ratio", "N/A"))
    col3.metric("ROE", reliance_metrics.get("ROE", "N/A"))
    col4.metric("Operating Margin", reliance_metrics.get("Operating Margin", "N/A"))

    # A second row for more metrics
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("EPS", f"₹{reliance_metrics.get('EPS', 'N/A')}")
    col6.metric("Book Value", f"₹{reliance_metrics.get('Book Value', 'N/A')}")
    col7.metric("Net Margin", reliance_metrics.get("Net Margin", "N/A"))
    col8.metric("P/B Ratio", "N/A") # You can add P/B extraction if needed
else:
    st.warning(f"Could not load Reliance metrics: {reliance_message}")

st.divider()  # A visual separator line

# --- Display Company List (Bottom Section) ---
st.subheader("📋 Top 10 Companies by Market Cap")

if company_df is None:
    st.error(list_message)
else:
    st.success(f"Successfully loaded {len(company_df)} companies.")
    st.dataframe(company_df.head(10), use_container_width=True)

    with st.expander("Click here to view all 5,159 companies"):
        st.dataframe(company_df, use_container_width=True)

    csv = company_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Full Company List as CSV",
        data=csv,
        file_name='annexure_companies.csv',
        mime='text/csv',
    )
