# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("10% Opportunity Scanner")

tab1, tab2, tab3 = st.tabs(["Scanner", "Manual Import", "Data Quality"])

with tab1:
    st.info("Opportunity Score and Entry Score results will be displayed here once the calculation specifications are confirmed.")

with tab2:
    uploaded = st.file_uploader("Upload TheAnnexure exported CSV/Excel", type=["csv", "xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.write("Original column names:", df.columns.tolist())
        st.dataframe(df.head(20))
        st.warning("Data can only be written to the database after validation. Missing fields will be marked as 'missing' and will NOT be filled with values from other sources.")

with tab3:
    st.write("This section will display: source, retrieval_date, reporting_period, and quality_status.")
