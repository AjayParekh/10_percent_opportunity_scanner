# app.py
import streamlit as st
import pandas as pd
from modules.database_manager import init_db, insert_metric_facts, get_all_metrics
from modules.data_validation import validate_annexure_frame
from config import SOURCE_ANNEXURE

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("10% Opportunity Scanner")

# Initialize DB on app start
init_db()

tab1, tab2, tab3 = st.tabs(["Scanner", "Manual Import", "Data Quality"])

with tab1:
    st.info("Opportunity Score and Entry Score results will be displayed here once the calculation specifications are confirmed.")

with tab2:
    st.header("TheAnnexure Data Import")
    st.write("Upload the exported CSV/Excel file. Missing values will be strictly marked as 'missing' and will NOT be filled from other sources.")
    
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        # Read file
        if uploaded_file.name.endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)
        else:
            raw_df = pd.read_excel(uploaded_file)
            
        st.subheader("1. Raw Data Preview")
        st.dataframe(raw_df.head())
        
        # Validate
        validated_df, report = validate_annexure_frame(raw_df)
        
        st.subheader("2. Validation Report")
        if report["status"] == "error":
            st.error(report["message"])
        else:
            st.success(f"Validation passed! {report['total_rows']} rows found.")
            if report['missing_values_count'] > 0:
                st.warning(f"⚠️ {report['missing_values_count']} rows have missing values. They will be marked as 'missing' in the database.")
            
            st.subheader("3. Processed Data Preview")
            st.dataframe(validated_df.head(10))
            
            # Save Button
            if st.button("Save Validated Data to Database"):
                success, msg = insert_metric_facts(validated_df, source=SOURCE_ANNEXURE)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

with tab3:
    st.header("Database Data Quality")
    st.write("This shows the actual data currently stored in your SQLite database.")
    
    db_data = get_all_metrics()
    if db_data.empty:
        st.info("No data in the database yet. Go to the 'Manual Import' tab to upload data.")
    else:
        # Filter options
        source_filter = st.multiselect("Filter by Source", options=db_data['source'].unique(), default=db_data['source'].unique())
        filtered_data = db_data[db_data['source'].isin(source_filter)]
        
        st.dataframe(filtered_data)
        
        # Show stats
        st.write(f"**Total Records:** {len(filtered_data)}")
        st.write(f"**Missing Quality Records:** {len(filtered_data[filtered_data['quality_status'] == 'missing'])}")
