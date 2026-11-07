import streamlit as st
import pandas as pd
import sqlite3
import json
import os
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

# If market is open, refresh every 1 hour (3600000 ms)
if is_weekday and is_market_hours:
    st_autorefresh(interval=3600000, key="market_hours_refresh")

# --- 2. PAGE SETUP & UI LAYER ---
st.set_page_config(page_title="Opportunity Scanner", layout="wide", page_icon="🏛️")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-app: #0A0D12;
        --bg-panel: #12161D;
        --border-hairline: #232A35;
        --text-primary: #E7EAEE;
        --text-secondary: #8891A0;
        --accent-gold: #C6992F;
    }

    .stApp { background-color: var(--bg-app); font-family: 'IBM Plex Sans', sans-serif; }
    [data-testid="stHeader"] { background-color: transparent; }
    .block-container { padding-top: 2rem; max-width: 1400px; }

    .omc-eyebrow {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        color: var(--accent-gold);
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }
    .omc-title {
        font-family: 'IBM Plex Sans', sans-serif;
        font-weight: 700;
        font-size: 2.05rem;
        color: var(--text-primary);
        margin: 0 0 0.35rem 0;
    }
    .omc-subtitle {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.95rem;
        color: var(--text-secondary);
        margin-bottom: 1.1rem;
    }
    
    div[data-testid="stDataFrame"] { border: 1px solid var(--border-hairline); border-radius: 3px; }
    
    div[data-testid="stMetric"] {
        background-color: var(--bg-panel);
        border: 1px solid var(--border-hairline);
        border-radius: 5px;
        padding: 15px;
    }
    div[data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--accent-gold) !important;
        font-weight: 700 !important;
    }
    hr { border-color: var(--border-hairline) !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# Status Banner
if is_weekday and is_market_hours:
    st.success("🟢 Market is OPEN. App will auto-refresh every 1 hour.")
else:
    st.info("🔴 Market is CLOSED. Auto-refresh is paused. You can manually refresh if needed.")

# --- 3. DATABASE SETUP ---
SNAPSHOT_DB = "market_snapshot.db"
TRACKER_DB = "portfolio_history.db"

def init_tracker():
    conn = sqlite3.connect(TRACKER_DB)
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

init_tracker()

# NO CACHE HERE: This ensures when the app refreshes, it reads the newest data from the DB
def get_snapshot_data():
    if os.path.exists(SNAPSHOT_DB):
        conn = sqlite3.connect(SNAPSHOT_DB)
        try:
            df = pd.read_sql_query("SELECT * FROM daily_snapshot ORDER BY score DESC", conn)
            conn.close()
            return df
        except: return pd.DataFrame()
    return pd.DataFrame()

def get_tracker_data():
    conn = sqlite3.connect(TRACKER_DB)
    df = pd.read_sql_query("SELECT * FROM tracker", conn)
    conn.close()
    return df

# --- 4. APP HEADER ---
st.markdown(
    """
    <div class="omc-eyebrow">Institutional Coverage · Data Matrix</div>
    <div class="omc-title">🏛️ Opportunity Scanner & Tracker</div>
    <div class="omc-subtitle">Real-time scraped data. Automatically updates daily via GitHub Actions.</div>
    """,
    unsafe_allow_html=True
)

df = get_snapshot_data()

# Create Tabs
tab1, tab2 = st.tabs(["🎯 Live Scanner & 10% Engine", "📈 Performance Tracker"])

# --- 5. TAB 1: LIVE SCANNER ---
with tab1:
    if df.empty:
        st.error("Database not found. Please run the GitHub Action to generate market_snapshot.db.")
    else:
        st.markdown("### 🎯 Top 3 Opportunities Today")
        
        top_3 = df.head(3)
        cols = st.columns(3)
        for idx, (_, row) in enumerate(top_3.iterrows()):
            target = row['price'] * 1.10
            with cols[idx]:
                st.metric(label=f"**{row['ticker']}**", value=f"₹{row['price']:.2f}", delta=f"Target: ₹{target:.2f}")
                st.caption(f"**Score:** {row['score']}/12 | **P/B:** {row['pb']} | **Drop:** {row['drop_52w']}")
                
                # HISTORICAL EDGE PREDICTION
                conn = sqlite3.connect(TRACKER_DB)
                past_trades = pd.read_sql_query(
                    f"SELECT days_active FROM tracker WHERE status='Achieved' AND json_extract(snapshot_json, '$.score') BETWEEN {row['score']-1} AND {row['score']+1}", 
                    conn
                )
                conn.close()
                
                if not past_trades.empty:
                    avg_days = past_trades['days_active'].mean()
                    st.info(f"🔮 **Historical Edge:** Similar setups took avg **{avg_days:.0f} days** to hit 10%.")
                else:
                    st.caption(f"🔮 *Not enough past data to predict timeframe.*")
                
                # SAVE BUTTON
                if st.button(f"💾 Track {row['ticker']}", key=f"btn_{row['ticker']}"):
                    snapshot = {
                        "score": int(row['score']), "pe": row['pe'], 
                        "pb": row['pb'], "roe": row['roe'], "drop_52w": row['drop_52w']
                    }
                    conn = sqlite3.connect(TRACKER_DB)
                    c = conn.cursor()
                    c.execute("SELECT id FROM tracker WHERE ticker=? AND date_logged=date('now')", (row['ticker'],))
                    if not c.fetchone():
                        c.execute("INSERT INTO tracker (date_logged, ticker, entry_price, target_price, status, snapshot_json) VALUES (date('now'), ?, ?, ?, 'Pending', ?)", 
                                  (row['ticker'], row['price'], target, json.dumps(snapshot)))
                        conn.commit()
                        st.success(f"Saved {row['ticker']} to Tracker!")
                    else:
                        st.warning(f"{row['ticker']} already saved today.")
                    conn.close()

        st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
        st.markdown("### 📋 Full Scanned Matrix (Top 100)")
        st.dataframe(
            df[['ticker', 'price', 'pe', 'pb', 'roe', 'drop_52w', 'score']].head(100),
            use_container_width=True,
            hide_index=True
        )

# --- 6. TAB 2: PERFORMANCE TRACKER ---
with tab2:
    st.markdown("### 📈 Historical Performance")
    tracker_df = get_tracker_data()
    
    if tracker_df.empty:
        st.info("No picks saved yet. Go to the Live Scanner and click 'Track'.")
    else:
        display_rows = []
        for _, row in tracker_df.iterrows():
            # Lookup current price from our daily snapshot (updated by GitHub Action)
            current_row = df[df['ticker'] == row['ticker']]
            current_price = current_row['price'].values[0] if not current_row.empty else row['entry_price']
            
            days_active = (datetime.now() - datetime.strptime(row['date_logged'], "%Y-%m-%d")).days
            return_pct = ((current_price - row['entry_price']) / row['entry_price']) * 100
            
            # Auto-update DB if target is hit
            if current_price >= row['target_price'] and row['status'] == 'Pending':
                conn = sqlite3.connect(TRACKER_DB)
                conn.execute("UPDATE tracker SET status='Achieved', days_active=? WHERE id=?", (days_active, row['id']))
                conn.commit()
                conn.close()
                status = "✅ Achieved!"
            else:
                status = "⏳ In Progress" if row['status'] == 'Pending' else row['status']
                
            display_rows.append({
                "Date": row['date_logged'], "Ticker": row['ticker'], "Entry": f"₹{row['entry_price']:.2f}",
                "Target": f"₹{row['target_price']:.2f}", "Current": f"₹{current_price:.2f}",
                "Return": f"{return_pct:+.2f}%", "Days": days_active, "Status": status
            })
            
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

# --- 7. MANUAL REFRESH BUTTON ---
st.markdown("<hr style='margin:1.5em 0;'>", unsafe_allow_html=True)
if st.button("🔄 Force Refresh Now"):
    st.rerun()
