import streamlit as st
import pandas as pd
import sqlite3
import json
import os
from datetime import datetime

st.set_page_config(page_title="10% Opportunity Scanner", layout="wide")

SNAPSHOT_DB = "market_snapshot.db"
TRACKER_DB = "portfolio_history.db"

# --- 1. INITIALIZE TRACKER DB ---
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

# --- 2. FETCH DATA ---
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

# --- 3. UI ---
st.title("🏛️ Opportunity Scanner & Tracker")
st.markdown("Scanning 5,000+ companies daily via GitHub Actions.")

df = get_snapshot_data()

tab1, tab2 = st.tabs(["🎯 Live Scanner", "📈 Performance Tracker"])

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

        st.divider()
        st.markdown("### 📋 Full Scanned Matrix (Top 100)")
        st.dataframe(
            df[['ticker', 'price', 'pe', 'pb', 'roe', 'drop_52w', 'score']].head(100),
            use_container_width=True,
            hide_index=True
        )

with tab2:
    st.markdown("### 📈 Historical Performance")
    tracker_df = get_tracker_data()
    
    if tracker_df.empty:
        st.info("No picks saved yet. Go to the Live Scanner and click 'Track'.")
    else:
        # Calculate live performance
        display_rows = []
        for _, row in tracker_df.iterrows():
            # Lookup current price from our daily snapshot
            current_row = df[df['ticker'] == row['ticker']]
            current_price = current_row['price'].values[0] if not current_row.empty else row['entry_price']
            
            days_active = (datetime.now() - datetime.strptime(row['date_logged'], "%Y-%m-%d")).days
            return_pct = ((current_price - row['entry_price']) / row['entry_price']) * 100
            
            # Update DB if hit
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
        
        # Optional download to back up tracker
        csv = tracker_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Backup Tracker DB (CSV)", csv, "tracker_backup.csv", "text/csv")
