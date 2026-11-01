# app.py
import streamlit as st
import pandas as pd
from modules.database_manager import init_db, insert_metric_facts, get_all_metrics
from scrapers.annexure_scraper import fetch_annexure_data
from config import SOURCE_ANNEXURE

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("10% Opportunity Scanner")

# Initialize DB on app start
init_db()

tab1, tab2, tab3 = st.tabs(["Scanner", "Automated Scraper", "Data Quality"])

with tab1:
    st.info("Opportunity Score and Entry Score results will be displayed here once the calculation specifications are confirmed.")

with tab2:
    st.header("TheAnnexure Automated Scraper")
    st.write("Enter the URL of the TheAnnexure page to scrape fundamental data.")
    
    url_input = st.text_input("TheAnnexure URL", placeholder="https://www.theannexure.com/...")
    
    if st.button("Start Scraping"):
        if not url_input:
            st.warning("Please enter a URL.")
        else:
            with st.spinner("Scraping data... Please wait."):
                # Run the scraper
                scraped_df = fetch_annexure_data(url_input)
                
                if scraped_df is None or scraped_df.empty:
                    st.error("Failed to scrape data. The page might be JavaScript-rendered, or the HTML structure has changed.")
                    st.info("Tip: Right-click the page -> Inspect Element to check if the data is inside an HTML table.")
                else:
                    st.success(f"Successfully scraped {len(scraped_df)} rows!")
                    
                    st.subheader("Preview of Scraped Data")
                    st.dataframe(scraped_df.head(10))
                    
                    # Save to Database
                    if st.button("Save Scraped Data to Database"):
                        success, msg = insert_metric_facts(scraped_df, source=SOURCE_ANNEXURE)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)

with tab3:
    st.header("Database Data Quality")
    st.write("This shows the actual data currently stored in your SQLite database.")
    
    db_data = get_all_metrics()
    if db_data.empty:
        st.info("No data in the database yet. Go to the 'Automated Scraper' tab to scrape data.")
    else:
        # Filter options
        source_filter = st.multiselect("Filter by Source", options=db_data['source'].unique(), default=db_data['source'].unique())
        filtered_data = db_data[db_data['source'].isin(source_filter)]
        
        st.dataframe(filtered_data)
        
        # Show stats
        st.write(f"**Total Records:** {len(filtered_data)}")
        st.write(f"**Missing Quality Records:** {len(filtered_data[filtered_data['quality_status'] == 'missing'])}")
