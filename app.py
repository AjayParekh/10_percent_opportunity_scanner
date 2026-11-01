import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# 1. Set up the page
st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("10% Opportunity Scanner")
st.write("Automated extraction of the company list from TheAnnexure.")

# 2. Define the scraping function
@st.cache_data(show_spinner=False)
def scrape_annexure_companies():
    url = "https://theannexure.com/companies.html"
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
    table = soup.find('table')
    
    if not table:
        return None, "Could not find an HTML table on the page. The website structure might have changed."

    rows = table.find_all('tr')
    if not rows:
        return None, "Table found, but it has no rows."

    headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
    
    data = []
    for row in rows[1:]:
        cols = [td.text.strip() for td in row.find_all('td')]
        if len(cols) == len(headers):
            data.append(cols)

    df = pd.DataFrame(data, columns=headers)
    return df, "Success"

# 3. Automatically fetch data when the app loads
with st.spinner("Fetching latest company list from TheAnnexure... Please wait."):
    df, message = scrape_annexure_companies()

# 4. Display the results
if df is None:
    st.error(message)
else:
    st.success(f"Successfully loaded {len(df)} companies!")
    
    # Show only the first 10 companies as requested
    st.subheader("Top 10 Companies by Market Cap")
    st.dataframe(df.head(10), use_container_width=True)
    
    # Optional: Put the full list in an expandable section so the page isn't too long
    with st.expander("Click here to view all 5,159 companies"):
        st.dataframe(df, use_container_width=True)
        
    # Provide the download button
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Full Company List as CSV",
        data=csv,
        file_name='annexure_companies.csv',
        mime='text/csv',
    )
