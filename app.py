import streamlit as st
import pandas as pd
import sqlite3
import os

st.set_page_config(page_title="Opportunity Scanner", layout="wide")
st.title("🏛️ Opportunity Scanner")
st.markdown("Data updated daily via automated GitHub Actions.")

SNAPSHOT_DB = "market_snapshot.db"

def get_data():
    if os.path.exists(SNAPSHOT_DB):
        try:
            conn = sqlite3.connect(SNAPSHOT_DB)
            df = pd.read_sql_query("SELECT * FROM daily_snapshot ORDER BY score DESC LIMIT 20", conn)
            conn.close()
            return df
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()

df = get_data()

if df.empty:
    st.error("Database not found or is empty! Please go to GitHub -> Actions -> Run Workflow.")
else:
    st.markdown("### 🎯 Top Opportunities Today")
    top_3 = df.head(3)
    cols = st.columns(3)
    for idx, (_, row) in enumerate(top_3.iterrows()):
        target = row['price'] * 1.10
        with cols[idx]:
            st.metric(label=f"**{row['ticker']}**", value=f"₹{row['price']:.2f}", delta=f"Target: ₹{target:.2f}")
            st.caption(f"**Score:** {row['score']}/12")
            st.caption(f"**P/B:** {row['pb']} | **Drop:** {row['drop_52w']}")
            
    st.divider()
    st.markdown("### 📋 Full Scanned Matrix")
    st.dataframe(df[['ticker', 'price', 'pe', 'pb', 'roe', 'drop_52w', 'score']], use_container_width=True, hide_index=True)
