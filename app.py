import streamlit as st
import pandas as pd
import sqlite3
import json
import os
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh
import requests
import base64

# --- 1. AUTO REFRESH LOGIC ---
ist = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(ist)
is_weekday = now_ist.weekday() < 5 
market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
is_market_hours = market_open <= now_ist <= market_close

if is_weekday and is_market_hours:
    st_autorefresh(interval=3600000, key="market_hours_refresh")

# --- 2. PAGE SETUP & UI ---
st.set_page_config(page_title="Opportunity Scanner", layout="wide", page_icon="🏛️")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
    :root { --bg-app: #0A0D12; --bg-panel: #12161D; --border-hairline: #232A35; --text-primary: #E7EAEE; --text-secondary: #8891A0; --accent-gold: #C6992F; }
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
    """, unsafe_allow_html=True
)

if is_weekday and is_market_hours:
    st.success("🟢 Market is OPEN. App will auto-refresh every 1 hour.")
else:
    st.info("🔴 Market is CLOSED. Auto-refresh is paused.")

# --- 3. GITHUB PERSISTENCE ---
REPO = "AjayParekh/10_percent_opportunity_scanner"
TRACKER_FILE = "portfolio_history.db"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

def load_db_from_github():
    if not GITHUB_TOKEN: return
    url = f"https://api.github.com/repos/{REPO}/contents/{TRACKER_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3.raw"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        with open(TRACKER_FILE, "wb") as f:
            f.write(res.content)

def save_db_to_github():
    if not GITHUB_TOKEN: 
        st.warning("No GITHUB_TOKEN found. Data will not be saved permanently.")
        return False
    
    url = f"https://api.github.com/repos/{REPO}/contents/{TRACKER_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    res = requests.get(url, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None
    
    with open(TRACKER_FILE, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
        
    data = {"message": "Streamlit Tracker Update", "content": content}
    if sha: data["sha"] = sha
        
    put_res = requests.put(url, headers=headers, json=data)
    return put_res.status_code in [200, 201]

load_db_from_github()

def init_tracker():
    conn = sqlite3.connect(TRACKER_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date_logged TEXT, ticker TEXT, 
        entry_price REAL, target_price REAL, status TEXT, days_active INTEGER, snapshot_json TEXT
    )''')
    conn.commit()
    conn.close()

init_tracker()

# --- 4. DATA FETCHING ---
SNAPSHOT_DB = "market_snapshot.db"

def get_snapshot_data():
    if os.path.exists(SNAPSHOT_DB):
        conn = sqlite3.connect(SNAPSHOT_DB)
        try:
            df = pd.read_sql_query("SELECT * FROM daily_snapshot", conn)
            conn.close()
            df['pb_float'] = pd.to_numeric(df['pb'], errors='coerce').fillna(999.0)
            df = df.sort_values(by=['score', 'pb_float'], ascending=[False, True]).drop(columns=['pb_float'])
            return df
        except: return pd.DataFrame()
    return pd.DataFrame()

def get_tracker_data():
    conn = sqlite3.connect(TRACKER_FILE)
    df = pd.read_sql_query("SELECT * FROM tracker ORDER BY date_logged DESC", conn)
    conn.close()
    return df

# --- 5. APP HEADER ---
st.markdown('<div class="omc-eyebrow">Institutional Coverage · Data Matrix</div>', unsafe_allow_html=True)
st.markdown('<div class="omc-title">🏛️ Opportunity Scanner & Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="omc-subtitle">Scanning Top 2000 companies with Sector-Specific Scoring.</div>', unsafe_allow_html=True)

df = get_snapshot_data()
tab1, tab2 = st.tabs(["🎯 Live Scanner & 10% Engine", "📈 Performance Tracker"])

# --- 6. TAB 1: LIVE SCANNER ---
with tab1:
    if df.empty:
        st.error("Database not found. Please run the GitHub Action.")
    else:
        st.sidebar.markdown("### 🏭 Sector Filter")
        all_sectors = ["All Sectors"] + sorted(df['sector'].dropna().unique().tolist())
        selected_sector = st.sidebar.selectbox("Choose Sector", all_sectors)
        
        filtered_df = df if selected_sector == "All Sectors" else df[df['sector'] == selected_sector]

        st.markdown(f"### 🎯 Top 3 Opportunities ({selected_sector})")
        top_3 = filtered_df.head(3)
        
        cols = st.columns(3)
        for idx, (_, row) in enumerate(top_3.iterrows()):
            target = row['price'] * 1.10
            with cols[idx]:
                st.metric(label=f"**{row['ticker']}** ({row['sector']})", value=f"₹{row['price']:.2f}", delta=f"Target: ₹{target:.2f}")
                
                # Show Book Value in the UI
                st.caption(f"**Score:** {row['score']}/15 | **P/B:** {row['pb']} | **BV:** ₹{row['book_value']:.2f} | **Drop:** {row['drop_52w']}")
                
                conn = sqlite3.connect(TRACKER_FILE)
                past_trades = pd.read_sql_query(
                    f"SELECT days_active FROM tracker WHERE status='Achieved' AND json_extract(snapshot_json, '$.score') BETWEEN {row['score']-2} AND {row['score']+2}", conn)
                conn.close()
                
                if not past_trades.empty:
                    st.info(f"🔮 **Historical Edge:** Similar setups took avg **{past_trades['days_active'].mean():.0f} days** to hit 10%.")
                else:
                    st.caption("🔮 *Not enough past data to predict timeframe.*")
                
                if st.button(f"💾 Track {row['ticker']}", key=f"btn_{row['ticker']}"):
                    snapshot = {
                        "score": int(row['score']), "pe": row['pe'], "pb": row['pb'], 
                        "book_value": row['book_value'], "roe": row['roe'], "drop_52w": row['drop_52w']
                    }
                    conn = sqlite3.connect(TRACKER_FILE)
                    c = conn.cursor()
                    # FIXED: Prevents tracking if it is already pending
                    c.execute("SELECT id FROM tracker WHERE ticker=? AND status='Pending'", (row['ticker'],))
                    if not c.fetchone():
                        c.execute("INSERT INTO tracker (date_logged, ticker, entry_price, target_price, status, snapshot_json) VALUES (date('now'), ?, ?, ?, 'Pending', ?)", 
                                  (row['ticker'], row['price'], target, json.dumps(snapshot)))
                        conn.commit()
                        conn.close()
                        with st.spinner("Saving permanently to GitHub..."):
                            if save_db_to_github():
                                st.success(f"Saved {row['ticker']} to GitHub History!")
                            else:
                                st.error("Failed to save to GitHub. Check your token.")
                    else:
                        st.warning(f"You are already tracking {row['ticker']} (Pending).")
                        conn.close()

        st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
        st.markdown(f"### 📋 Full Scanned Matrix - {selected_sector} (Top 100)")
        
        # Added Book Value to display
        display_cols = ['ticker', 'sector', 'price', 'pe', 'pb', 'book_value', 'roe', 'drop_52w', 'score']
        st.dataframe(filtered_df[display_cols].head(100), use_container_width=True, hide_index=True)

# --- 7. TAB 2: PERFORMANCE TRACKER ---
with tab2:
    st.markdown("### 📈 Historical Performance")
    st.markdown("This table shows every stock you've ever tracked, including its exact metrics on the day you tracked it.")
    
    tracker_df = get_tracker_data()
    
    if tracker_df.empty:
        st.info("No picks saved yet. Go to the Live Scanner and click 'Track'.")
    else:
        display_rows = []
        for _, row in tracker_df.iterrows():
            current_row = df[df['ticker'] == row['ticker']]
            current_price = current_row['price'].values[0] if not current_row.empty else row['entry_price']
            
            days_active = (datetime.now() - datetime.strptime(row['date_logged'], "%Y-%m-%d")).days
            return_pct = ((current_price - row['entry_price']) / row['entry_price']) * 100 if row['entry_price'] > 0 else 0
            
            status_updated = False
            if current_price >= row['target_price'] and row['status'] == 'Pending':
                conn = sqlite3.connect(TRACKER_FILE)
                conn.execute("UPDATE tracker SET status='Achieved', days_active=? WHERE id=?", (days_active, row['id']))
                conn.commit()
                conn.close()
                status = "✅ Achieved!"
                status_updated = True
            else:
                status = "⏳ In Progress" if row['status'] == 'Pending' else row['status']
                
            # Parse the snapshot JSON to show historical metrics
            try:
                snap = json.loads(row['snapshot_json'])
                entry_score = snap.get('score', 'N/A')
                entry_pb = snap.get('pb', 'N/A')
                entry_roe = snap.get('roe', 'N/A')
            except:
                entry_score, entry_pb, entry_roe = 'N/A', 'N/A', 'N/A'
                
            display_rows.append({
                "Date Logged": row['date_logged'], 
                "Ticker": row['ticker'], 
                "Entry": f"₹{row['entry_price']:.2f}",
                "Target": f"₹{row['target_price']:.2f}", 
                "Current": f"₹{current_price:.2f}",
                "Return": f"{return_pct:+.2f}%", 
                "Days": days_active, 
                "Status": status,
                "Entry Score": entry_score,
                "Entry P/B": entry_pb,
                "Entry ROE": entry_roe
            })
            
        if status_updated:
            save_db_to_github()
            
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

# --- 8. MANUAL REFRESH ---
st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
if st.button("🔄 Force Refresh Now"):
    st.rerun()
