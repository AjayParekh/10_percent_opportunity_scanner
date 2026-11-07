import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import concurrent.futures
import os
import sqlite3
import json
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. AUTO REFRESH LOGIC (INDIAN MARKET HOURS) ---
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist)
is_weekday = now_ist.weekday() < 5 
market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
is_market_hours = market_open <= now_ist <= market_close

if is_weekday and is_market_hours:
    st_autorefresh(interval=3600000, key="market_hours_refresh") # Refresh every 1 hr

# --- 2. DATABASE SETUP (SQLite) ---
DB_FILE = "opportunity_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_logged TEXT,
            ticker TEXT,
            entry_price REAL,
            target_price REAL,
            status TEXT,
            days_active INTEGER,
            snapshot_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_FILE)

init_db()

# --- 3. PAGE SETUP & UI LAYER ---
st.set_page_config(page_title="Opportunity Scanner", layout="wide", page_icon="🏛️")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    :root {
        --bg-app: #0A0D12; --bg-panel: #12161D; --border-hairline: #232A35;
        --text-primary: #E7EAEE; --text-secondary: #8891A0; --accent-gold: #C6992F;
    }
    .stApp { background-color: var(--bg-app); font-family: 'IBM Plex Sans', sans-serif; }
    [data-testid="stHeader"] { background-color: transparent; }
    .block-container { padding-top: 2rem; max-width: 1400px; }
    .omc-eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 0.18em; color: var(--accent-gold); text-transform: uppercase; margin-bottom: 0.3rem; }
    .omc-title { font-family: 'IBM Plex Sans', sans-serif; font-weight: 700; font-size: 2.05rem; color: var(--text-primary); margin: 0 0 0.35rem 0; }
    .omc-subtitle { font-family: 'IBM Plex Sans', sans-serif; font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 1.1rem; }
    
    div[data-testid="stDataFrame"] { border: 1px solid var(--border-hairline); border-radius: 3px; }
    div[data-testid="stMetric"] { background-color: var(--bg-panel); border: 1px solid var(--border-hairline); border-radius: 5px; padding: 15px; }
    div[data-testid="stMetric"] label { color: var(--text-secondary) !important; font-family: 'IBM Plex Mono', monospace !important; }
    div[data-testid="stMetricValue"] { color: var(--accent-gold) !important; font-weight: 700 !important; }
    hr { border-color: var(--border-hairline) !important; }
    </style>
    """,
    unsafe_allow_html=True
)

if is_weekday and is_market_hours:
    st.success("🟢 Market is OPEN. App will auto-refresh every 1 hour.")
else:
    st.info("🔴 Market is CLOSED. Auto-refresh is paused.")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

def robust_numeric_parse(val_str):
    if not val_str or pd.isna(val_str): return 0.0
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val_str).replace(',', '').strip())
        return float(cleaned) if cleaned else 0.0
    except: return 0.0

# --- 4. SCRAPERS ---
@st.cache_data(ttl=300)
def fetch_google_finance_live_data(ticker: str):
    url = f"https://www.google.com/finance/beta/quote/{ticker}:NSE?tab=financials"
    metrics = {"price_str": "N/A", "price_val": 0.0, "pct_change_str": "N/A", "abs_change_str": "N/A"}
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        price_el = soup.find(attrs={"data-last-price": True}) or soup.find(class_="YMlKec fxKbKc")
        if not price_el:
            for div in soup.find_all("div"):
                if div.text and div.text.strip().startswith("₹") and len(div.text.strip()) < 15:
                    price_el = div
                    break
        if price_el:
            metrics["price_str"] = price_el.text.strip()
            metrics["price_val"] = robust_numeric_parse(metrics["price_str"])
        full_text = re.sub(r'\s+', ' ', soup.get_text(separator=" "))
        change_pattern = re.search(r'([+-]?\d+\.\d+)\s*%\s*\(\s*([+-]?[\d,]+\.\d+)\s*\)\s*1D', full_text)
        if change_pattern:
            metrics["pct_change_str"] = f"{change_pattern.group(1)}%"
            metrics["abs_change_str"] = change_pattern.group(2)
    except: pass
    return metrics

@st.cache_data(ttl=3600)
def fetch_annexure_all_details(bse_code: str):
    url = f"https://theannexure.com/company/{bse_code}.html"
    data = {}
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        mc = re.search(r"Market cap ₹([\d,\.]+) cr", text)
        if mc: data["Market Cap"] = f"₹{mc.group(1)} Cr"
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            data["P/E Ratio"] = f"{pe_pb.group(1)}×"
            data["P/B Ratio"] = f"{pe_pb.group(2)}×"
            
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = re.sub(r'\s+', ' ', cells[0].get_text(strip=True))
                    val = re.sub(r'\s+', ' ', cells[1].get_text(strip=True))
                    if label and val and label.lower() not in ["metric", "ratio", "period"]:
                        if label not in data: data[label] = val
    except: pass
    return data

# --- 5. COMPANIES LIST (PASTE YOUR FULL 100+ LIST HERE) ---
COMPANIES = [
    {"name": "Reliance Industries Ltd", "ticker": "RELIANCE", "bse": "500325", "industry": "Energy"},
    {"name": "Bank of India", "ticker": "BANKINDIA", "bse": "532149", "industry": "Banking"},
    {"name": "Tata Consultancy Services", "ticker": "TCS", "bse": "532540", "industry": "IT"},
    {"name": "HDFC Bank Ltd", "ticker": "HDFCBANK", "bse": "500180", "industry": "Banking"},
    {"name": "Vedanta Ltd", "ticker": "VEDL", "bse": "500295", "industry": "Metals"},
    # --> PASTE THE REST OF YOUR 100+ COMPANIES HERE <--
]

def fetch_company_data(comp):
    gf = fetch_google_finance_live_data(comp["ticker"])
    annex = fetch_annexure_all_details(comp["bse"])
    return comp, gf, annex

# --- 6. PARALLEL FETCHING ---
with st.spinner("Scanning market data for 100+ companies..."):
    table_rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_company_data, COMPANIES))

    for comp, gf, annex in results:
        row = {
            "Company Name": comp["name"],
            "Ticker": comp["ticker"],
            "Current Price": gf["price_str"],
            "Price_Val": gf["price_val"],
            "Change %": gf["pct_change_str"],
            "P/E Ratio": annex.get("P/E Ratio", "N/A"),
            "P/B Ratio": annex.get("P/B Ratio", "N/A"),
            "ROE": annex.get("Return on equity", "N/A"),
            "52W High Drop": annex.get("Against 52-week high", "N/A"),
            "Industry": comp["industry"]
        }
        table_rows.append(row)

df_display = pd.DataFrame(table_rows)

# --- 7. CALCULATIONS ---
def parse_pct(val):
    if not isinstance(val, str) or val == "N/A": return 0.0
    try: return float(val.replace('%', '').replace('+', '').strip())
    except: return 0.0

df_display['_pe'] = df_display['P/E Ratio'].apply(robust_numeric_parse)
df_display['_pb'] = df_display['P/B Ratio'].apply(robust_numeric_parse)
df_display['_roe'] = df_display['ROE'].apply(robust_numeric_parse)
df_display['_drop'] = df_display['52W High Drop'].apply(parse_pct)

def calculate_score(row):
    score = 0
    if 0 < row['_pb'] < 1.0: score += 4
    elif 1.0 <= row['_pb'] < 1.5: score += 2
    if 0 < row['_pe'] < 20: score += 2
    if row['_drop'] < -15: score += 3
    if row['_roe'] > 15: score += 3
    return score

df_display['Score'] = df_display.apply(calculate_score, axis=1)
candidates = df_display[df_display['Score'] >= 5].sort_values(by='Score', ascending=False)

# --- 8. UI RENDERING ---
st.markdown('<div class="omc-eyebrow">Institutional Coverage · Matrix</div>', unsafe_allow_html=True)
st.markdown('<div class="omc-title">🏛️ Opportunity Scanner & Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="omc-subtitle">Real-time scraped data. Over 100 companies tracked.</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 Live Scanner & 10% Engine", "📈 Performance Tracker"])

with tab1:
    st.markdown("### 🎯 Top Picks for ~10% Return (1-2 Months)")
    
    top_picks = candidates.head(3)
    if not top_picks.empty:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(top_picks.iterrows()):
            target = row['Price_Val'] * 1.10
            with cols[idx]:
                st.metric(f"🏆 {row['Ticker']} ({row['Industry']})", f"Target: ₹{target:.2f}", f"Current: ₹{row['Price_Val']:.2f}")
                
                # HISTORICAL PREDICTION LOGIC
                conn = get_db_connection()
                past_trades = pd.read_sql_query(
                    f"SELECT days_active FROM tracker WHERE status='Achieved' AND json_extract(snapshot_json, '$.score') BETWEEN {row['Score']-1} AND {row['Score']+1}", 
                    conn
                )
                conn.close()
                
                if not past_trades.empty:
                    avg_days = past_trades['days_active'].mean()
                    st.caption(f"🔮 **Historical Edge:** Similar setups took avg **{avg_days:.0f} days** to hit 10%.")
                else:
                    st.caption(f"🔮 **Historical Edge:** Not enough past data for Score {row['Score']}.")
                
                st.caption(f"Score: {row['Score']}/12 | P/B: {row['P/B Ratio']} | Drop: {row['52W High Drop']}")

        if st.button("💾 Save Top 3 Picks to Tracker"):
            conn = get_db_connection()
            c = conn.cursor()
            for _, row in top_picks.iterrows():
                snapshot = {"score": int(row['Score']), "pe": row['P/E Ratio'], "pb": row['P/B Ratio'], "roe": row['ROE'], "drop_52w": row['52W High Drop']}
                c.execute("SELECT id FROM tracker WHERE ticker=? AND date_logged=date('now')", (row['Ticker'],))
                if not c.fetchone():
                    c.execute("INSERT INTO tracker (date_logged, ticker, entry_price, target_price, status, snapshot_json) VALUES (date('now'), ?, ?, ?, 'Pending', ?)", 
                              (row['Ticker'], row['Price_Val'], row['Price_Val']*1.10, json.dumps(snapshot)))
            conn.commit()
            conn.close()
            st.success("Picks permanently saved to SQLite database!")
            st.rerun()

    st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
    st.markdown("### 📋 Full Institutional Data Matrix")
    st.dataframe(df_display.drop(columns=['Price_Val', '_pe', '_pb', '_roe', '_drop']), use_container_width=True, hide_index=True)

with tab2:
    st.markdown("### 📈 Live Performance Tracker")
    conn = get_db_connection()
    tracker_df = pd.read_sql_query("SELECT * FROM tracker", conn)
    conn.close()
    
    if tracker_df.empty:
        st.info("No picks saved yet. Go to the Live Scanner tab to save your top picks!")
    else:
        display_rows = []
        for _, row in tracker_df.iterrows():
            live = fetch_google_finance_live_data(row['ticker'])
            current_price = live['price_val']
            days_active = (datetime.now() - datetime.strptime(row['date_logged'], "%Y-%m-%d")).days
            
            if current_price > 0:
                return_pct = ((current_price - row['entry_price']) / row['entry_price']) * 100
                if current_price >= row['target_price'] and row['status'] == 'Pending':
                    conn = get_db_connection()
                    conn.execute("UPDATE tracker SET status='Achieved', days_active=? WHERE id=?", (days_active, row['id']))
                    conn.commit()
                    conn.close()
                    status = "✅ Goal Achieved!"
                else:
                    status = row['status'] if row['status'] != 'Pending' else "⏳ In Progress"
                    
                display_rows.append({
                    "Date": row['date_logged'], "Ticker": row['ticker'], "Entry": f"₹{row['entry_price']:.2f}",
                    "Target": f"₹{row['target_price']:.2f}", "Current": f"₹{current_price:.2f}",
                    "Return": f"{return_pct:+.2f}%", "Days": days_active, "Status": status,
                    "Snapshot Score": json.loads(row['snapshot_json'])['score']
                })
        
        if display_rows:
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

# Refresh Button
st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
if st.button("🔄 Refresh Live Data"):
    st.cache_data.clear()
    st.rerun()
