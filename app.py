# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")
st.title("10% Opportunity Scanner")

tab1, tab2, tab3 = st.tabs(["Scanner", "Manual Import", "Data Quality"])

with tab1:
    st.info("Opportunity Score 与 Entry Score 的计算规范确认后将在此展示结果。")

with tab2:
    uploaded = st.file_uploader("上传 TheAnnexure 导出的 CSV/Excel", type=["csv", "xlsx"])
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        st.write("原始列名：", df.columns.tolist())
        st.dataframe(df.head(20))
        st.warning("校验通过后才可写入数据库；缺失字段将标记为 missing，不会用其他来源补值。")

with tab3:
    st.write("此处将显示 source、retrieval_date、reporting_period、quality_status。")
