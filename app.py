import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- 1. PAGE SETUP & UI LAYER (Matches your reference) ---
st.set_page_config(page_title="Reliance - 10% Opportunity Scanner", layout="wide", page_icon="🏛️")

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
        --signal-green: #34D399;
        --signal-red: #F87171;
    }

    .stApp {
        background-color: var(--bg-app);
        font-family: 'IBM Plex Sans', sans-serif;
    }
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
        letter-spacing: -0.01em;
        margin: 0 0 0.35rem 0;
    }
    .omc-subtitle {
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 0.95rem;
        color: var(--text-secondary);
        margin-bottom: 1.1rem;
    }

    div[data-testid="stDataFrame"] {
        filter: none !important;
        opacity: 1 !important;
        transition: none !important;
        border: 1px solid var(--border-hairline) !important;
        border-radius: 3px !important;
    }
    #root .stStatusWidget { display: none !important; }
    hr { border-color: var(--border-hairline) !important; }
    </style>
    """,
    unsafe_allow_html=True
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def robust_numeric_parse(val_str):
    if not val_str or pd.isna(val_str): return 0.0
    try:
        cleaned = re.sub(r'[^\d.-]', '', str(val_str).replace(',', '').strip())
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

# --- 2. GOOGLE FINANCE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_google_finance_live_data():
    url = "https://www.google.com/finance/beta/quote/RELIANCE:NSE?tab=financials"
    metrics = {"price_str": "N/A", "price_val": 0.0, "pct_change_str": "N/A", "abs_change_str": "N/A"}
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200: return metrics
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

        change_pattern_pct_first = re.search(r'([+-]?\d+\.\d+)\s*%\s*\(\s*([+-]?[\d,]+\.\d+)\s*\)\s*1D', full_text)
        change_pattern_abs_first = re.search(r'\(\s*([+-]?[\d,]+\.\d+)\s*\)\s*([+-]?\d+\.\d+)\s*%\s*1D', full_text)

        pct_part, abs_part = None, None
        if change_pattern_pct_first:
            pct_part, abs_part = change_pattern_pct_first.group(1), change_pattern_pct_first.group(2)
        elif change_pattern_abs_first:
            abs_part, pct_part = change_pattern_abs_first.group(1), change_pattern_abs_first.group(2)

        if pct_part and abs_part:
            metrics["pct_change_str"] = f"{pct_part}%"
            metrics["abs_change_str"] = abs_part
        else:
            change_text = ""
            if price_el:
                parent = price_el.find_parent()
                if parent:
                    sibling_divs = parent.find_all(string=re.compile(r'%'))
                    if sibling_divs: change_text = sibling_divs[0].strip()
            if change_text:
                clean_text = change_text.replace("Today", "").replace("After hours", "").strip()
                extracted_metrics = re.findall(r'([+-]?\d+(?:\.\d+)?%?)', clean_text)
                if extracted_metrics: metrics["pct_change_str"] = extracted_metrics[0]
            
            try:
                if metrics["price_val"] > 0 and metrics["pct_change_str"] != "N/A":
                    raw_pct = float(re.sub(r'[^\d.-]', '', metrics["pct_change_str"]))
                    prev_close = metrics["price_val"] / (1 + (raw_pct / 100.0))
                    calculated_abs_change = metrics["price_val"] - prev_close
                    metrics["abs_change_str"] = f"{'+' if calculated_abs_change > 0 else ''}{calculated_abs_change:.2f}"
            except Exception: pass
    except Exception: pass
    return metrics


# --- 3. THEANNEXURE SCRAPER ---
@st.cache_data(ttl=3600)
def fetch_annexure_all_details():
    url = "https://theannexure.com/company/500325.html"
    data = {}
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')
        text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
        
        # Regex for Top Summary
        mc = re.search(r"Market cap ₹([\d,\.]+) cr", text)
        if mc: data["Market Cap"] = f"₹{mc.group(1)} Cr"
        
        pe_pb = re.search(r"P/E · P/B ([\d\.]+)× · ([\d\.]+)×", text)
        if pe_pb:
            data["Stock P/E"] = f"{pe_pb.group(1)}×"
            data["P/B Ratio"] = f"{pe_pb.group(2)}×"
            
        eps = re.search(r"EPS ₹([\d\.]+)", text)
        if eps: data["EPS"] = f"₹{eps.group(1)}"
        
        bv = re.search(r"BV ₹([\d\.]+)", text)
        if bv: data["Book Value"] = f"₹{bv.group(1)}"

        # Regex for Tables
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = re.sub(r'\s+', ' ', cells[0].get_text(strip=True))
                    val = re.sub(r'\s+', ' ', cells[1].get_text(strip=True))
                    
                    if label and val and label.lower() not in ["metric", "ratio", "period"]:
                        # Standardize names for our matrix
                        if "Return on equity" in label: data["ROE"] = val
                        elif "Debt to Equity" in label: data["Debt / Equity"] = val
                        elif "Operating margin" in label: data["Operating Margin"] = val
                        elif "Net margin" in label: data["Net Margin"] = val
                        elif "Against 52-week high" in label: data["52W High %"] = val
                        elif "Against 52-week low" in label: data["52W Low %"] = val
                        else:
                            if label not in data:
                                data[label] = val
                            
    except Exception as e:
        st.error(f"Error scraping TheAnnexure: {e}")
        
    return data


# --- 4. BUILD THE HORIZONTAL MATRIX ROW ---
# Fetch Data
with st.spinner("Fetching live data from Google Finance and TheAnnexure..."):
    gf = fetch_google_finance_live_data()
    ax = fetch_annexure_all_details()

# Combine into the exact column structure from your reference
row_data = {
    "Sr. No.": 1,
    "Composite Rec": "⏳ WAIT", # Placeholder for your 10% logic later
    "Ticker": "RELIANCE",
    "Company Name": "Reliance Industries Ltd",
    "Entry Status": "⏳ WAIT (Need Math)", 
    "Ideal Entry Range": "N/A",
    "Trend Position": "Mid-Range (Neutral)",
    "Engine Signal": "⚪ WATCH",
    "Quality Filter": "N/A",
    "Upside Target %": "N/A",
    "Low PE Alert": "⚪ WAIT",
    "BSE Group": "A",
    "Current Price": gf["price_str"],
    "Chg / Chg %": f"{gf['abs_change_str']} ({gf['pct_change_str']})",
    "52W High": ax.get("52W High", "N/A"), # Will fallback to N/A if not found
    "52W Low": ax.get("52W Low", "N/A"),
    "Stock P/E": ax.get("Stock P/E", "N/A"),
    "P/B Ratio": ax.get("P/B Ratio", "N/A"),
    "Book Value": ax.get("Book Value", "N/A"),
    "Debt / Equity": ax.get("Debt / Equity", "N/A"),
    "ROE": ax.get("ROE", "N/A"),
    "Market Cap": ax.get("Market Cap", "N/A"),
}

# Convert to DataFrame
df_matrix = pd.DataFrame([row_data])

# Styling Functions (Same as your reference)
def _style_signal(val):
    text = str(val)
    if "STRONG BUY" in text or "🚀" in text or "🟢" in text:
        return "background-color: rgba(52,211,153,0.12); color:#34D399; font-weight:600;"
    if "🔴" in text:
        return "background-color: rgba(248,113,113,0.10); color:#F87171; font-weight:600;"
    if "⚪" in text or "WATCH" in text:
        return "color:#8891A0;"
    return ""

def _style_signed_pct(val):
    try:
        num = float(str(val).replace("%", "").replace("⚠️", "").replace("▲", "").strip())
        if num > 0: return "color:#34D399;"
        if num < 0: return "color:#F87171;"
    except Exception: pass
    return ""

signal_cols = ["Composite Rec", "Engine Signal", "Quality Filter", "Low PE Alert", "Entry Status"]
signed_pct_cols = ["Chg / Chg %", "Upside Target %"]

styled_df = df_matrix.style
style_fn = getattr(styled_df, "map", None) or styled_df.applymap
if signal_cols:
    styled_df = style_fn(_style_signal, subset=signal_cols)
    style_fn = getattr(styled_df, "map", None) or styled_df.applymap
if signed_pct_cols:
    styled_df = style_fn(_style_signed_pct, subset=signed_pct_cols)

# --- 5. MAIN APP LAYOUT ---
st.markdown(
    """
    <div class="omc-eyebrow">Cross-Strategy Overlay</div>
    <div class="omc-title" style="font-size:1.4rem;">🏛️ Integrated Institutional Strategy Matrix</div>
    <div class="omc-subtitle">Cross-strategy asset valuation overlay – the <b>Composite Rec</b> merges Engine, Filter, Target & Flag. <b>Entry Status</b> and <b>Ideal Entry Range</b> prevent bad timing.</div>
    """,
    unsafe_allow_html=True
)

# Display the Horizontal Table
st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    height=150 # Compact height for a single row
)

# Display raw source data in an expander so you can verify it
with st.expander("🔍 View Raw Scraped Data (Audit Trail)"):
    st.write("**Google Finance:**", gf)
    st.write("**TheAnnexure:**", ax)

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()
