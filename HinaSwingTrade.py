import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import numpy as np # Robust NaN handling for yfinance multi-index

# --- PAGE SETUP ---
st.set_page_config(page_title="Hina Swing Trade AI", layout="wide")

# --- SECRETS (Ab sirf Telegram chahiye) ---
try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    CHAT_ID = st.secrets["CHAT_ID"]
except:
    st.warning("⚠️ Security Alert: Streamlit Secrets mein Telegram Token aur Chat ID set nahi hain.")
    st.stop()

WATCHLIST_FILE = "HinaSwingTrade.txt"

# --- HELPER FUNCTIONS FOR ROBUST DATA ACCESS (yfinance multi-index fixes) ---
def get_safe_series(df, col_name):
    """Safely gets a single Series from a potentially MultiIndex yfinance DataFrame."""
    try:
        # Standard yfinance format: df[('Close', 'Ticker')] or flattened df['Close']
        if col_name in df.columns:
            return df[col_name]
        
        # If columns are MultiIndex, get only the data level Series (ignoring Ticker index)
        if isinstance(df.columns, pd.MultiIndex):
            if df.columns.nlevels > 1:
                return df.xs(col_name, level=0, axis=1) # XS gets cross-section, often a DF but hopefully with 1 column if downloaded only 1 ticker
        
        # Fallback if nothing else works, though less safe
        if col_name in df.columns.get_level_values(0):
            return df[col_name]
    except Exception as e:
        st.error(f"Error accessing column {col_name}: {e}")
    return pd.Series(dtype=float)

def get_latest_float(series):
    """Safely extracts the last valid float value from a Series or Series-like object."""
    try:
        if isinstance(series, pd.DataFrame):
            # If multi-index somehow persisted, get first column
            series = series.iloc[:, 0]
        
        if series.empty:
            return np.nan

        # Get last value (handle series vs single value iloc return)
        val = series.iloc[-1]
        if isinstance(val, pd.Series):
             return float(val.iloc[0])
        else:
             return float(val)
    except Exception as e:
        return np.nan # Graceful error handling for missing data

# --- 1. LIVE CLOCK (Top Right Corner) ---
clock_widget = """
<div id="clock" style="
    position: fixed;
    top: 15px;
    right: 20px;
    background-color: #1E1E1E;
    color: #00FF00;
    padding: 8px 15px;
    border-radius: 8px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 16px;
    font-weight: bold;
    z-index: 99999;
    box-shadow: 0px 4px 6px rgba(0,0,0,0.5);
    border: 1px solid #00FF00;
"></div>
<script>
    function updateTime() {
        var now = new Date();
        var timeString = now.toLocaleDateString('en-IN') + ' | ' + now.toLocaleTimeString('en-IN', { hour12: true });
        document.getElementById('clock').innerHTML = '🕒 ' + timeString;
    }
    setInterval(updateTime, 1000);
    updateTime();
</script>
"""
st.markdown(clock_widget, unsafe_allow_html=True)

# --- 2. SIDEBAR NOTEPAD ---
st.sidebar.title("🛠️ Tools Menu")
st.sidebar.markdown("---")
st.sidebar.subheader("📝 Personal Notepad")

# Notepad ko session state me save rakhne ke liye
if 'notepad_text' not in st.session_state:
    st.session_state['notepad_text'] = ""

notes = st.sidebar.text_area("Yahan notes likhein (Niche se khinch kar bada karein):", value=st.session_state['notepad_text'], height=250)
st.session_state['notepad_text'] = notes

# --- SECTOR INDICES ---
SECTORS = {
    "^NSEBANK": "NIFTY BANK",
    "^CNXFMCG": "NIFTY FMCG",
    "^CNXIT": "NIFTY IT",
    "^CNXMETAL": "NIFTY METAL",
    "^CNXPHARMA": "NIFTY PHARMA",
    "^CNXPSUBANK": "NIFTY PSU"
}

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except: pass

def get_stock_index(ticker):
    bank = ['HDFCBANK', 'ICICIBANK', 'SBIN', 'AXISBANK', 'KOTAKBANK', 'INDUSINDBK', 'BANKBARODA', 'PNB', 'FEDERALBNK', 'AUBANK', 'CANBK']
    it = ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM', 'LTIM']
    metal = ['TATASTEEL', 'HINDALCO', 'JSWSTEEL', 'VEDL', 'COALINDIA']
    fmcg = ['ITC', 'HINDUNILVR', 'NESTLEIND', 'BRITANNIA', 'GODREJCP', 'DABUR', 'MARICO']
    
    t = ticker.replace('.NS', '')
    if t in bank: return "BankNifty"
    elif t in it: return "Nifty IT"
    elif t in metal: return "Nifty Metal"
    elif t in fmcg: return "Nifty FMCG"
    else: return "Nifty 50/Mid"

# --- 4. SIGNAL STYLING FUNCTION (LITE HOLD FIX) ---
def color_signal(val):
    """styles the SIGNAL column cell background."""
    background_style = ''
    text_style = ''
    
    if val == '✅ BUY':
        # Green background with some opacity
        background_style = 'background-color: rgba(30, 255, 30, 0.6);' 
        text_style = 'color: white;' # White text for contrast
    elif val == '❌ SELL':
        # Red background with some opacity
        background_style = 'background-color: rgba(255, 30, 30, 0.6);' 
        text_style = 'color: white;' # White text for contrast
    elif val == '⏳ HOLD':
        # CURRENT FIX: VERY lite background (approx 15% opacity amber/orange)
        background_style = 'background-color: rgba(255, 165, 0, 0.15);' 
        # Optional: Set a specific text color to keep it orange
        text_style = 'color: #FFA500;' # Distinct Orange text
        
    return f"{background_style} {text_style}"

def analyze_stock(ticker):
    try:
        # SINGLE ticker download for robustness
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 75: return None

        # Robust access fixes for analyze_stock (fixes yfinance multi-index errors)
        close_series = get_safe_series(df, 'Close')
        volume_series = get_safe_series(df, 'Volume')
        low_series = get_safe_series(df, 'Low')
        high_series = get_safe_series(df, 'High')

        # Recalculating all based on standardized safe Series
        ema9_series = close_series.ewm(span=9, adjust=False).mean()
        ema20_series = close_series.ewm(span=20, adjust=False).mean()
        ema75_series = close_series.ewm(span=75, adjust=False).mean()
        vol_avg_series = volume_series.rolling(window=15).mean()
        supp_series = low_series.rolling(window=15).min()
        res_series = high_series.rolling(window=15).max()

        # Extract last valid valid floats safely
        close = get_latest_float(close_series)
        e9 = get_latest_float(ema9_series)
        e20 = get_latest_float(ema20_series)
        e75 = get_latest_float(ema75_series)
        
        vol_today = get_latest_float(volume_series)
        vol_avg = get_latest_float(vol_avg_series)
        
        # Safe float checks
        if np.isnan(close) or np.isnan(e20) or np.isnan(e75):
            return None # Missing core data
            
        vol_x = (vol_today / vol_avg) if (vol_avg > 0 and not np.isnan(vol_avg)) else 0
        supp = get_latest_float(supp_series)
        res = get_latest_float(res_series)
        
        index_name = get_stock_index(ticker)
        clean_t = ticker.replace('.NS', '')

        signal = "⏳ HOLD"
        if (e9 > e20 > e75) and (vol_x > 3) and (close > e20):
            signal = "✅ BUY"
            send_telegram_msg(f"✅ BUY SIGNAL\nStock: {clean_t}\nSector: {index_name}\nPrice: ₹{close:.2f}\nTarget: ₹{res:.2f}\nSL: ₹{supp:.2f}\nVol: {vol_x:.1f}x")
        elif close < e20:
            signal = "❌ SELL"

        return {
            "STOCK": f"{clean_t} ({index_name})", "PRICE": round(close, 2), 
            "EMA-9": round(e9, 2), "EMA-20": round(e20, 2), "EMA-75": round(e75, 2),
            "SUPPORT": round(supp, 2), "TARGET": round(res, 2), 
            "VOL(x)": round(vol_x, 1), "SIGNAL": signal
        }
    except Exception as e: 
        return None

# --- MAIN DASHBOARD ---
st.title("🚀 Hina Swing Trade - AI Terminal")

st.markdown("---")
st.subheader("📊 Sectoral Indices Heatmap (Live)")

tickers = list(SECTORS.keys())
data = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
cols = st.columns(len(SECTORS))

for i, (ticker, name) in enumerate(SECTORS.items()):
    try:
        # Robust access fixes for Sector Heatmap (fixes yfinance multi-index errors)
        # Sector indices download often returns multi-index DF for Close
        ticker_data = data[ticker] if ticker in data.columns else None
        
        # Robust retrieval of close prices
        if ticker_data is not None and isinstance(ticker_data, pd.Series):
             today_close = float(ticker_data.iloc[-1])
             yest_close = float(ticker_data.iloc[-2])
        elif ticker_data is not None and isinstance(ticker_data, pd.DataFrame):
             today_close = float(ticker_data.iloc[-1].iloc[0]) # Get first ticker close if multi-index somehow persisted
             yest_close = float(ticker_data.iloc[-2].iloc[0])
        else:
             cols[i].metric(label=name, value="Error", delta=None)
             continue
        
        # Change Calculation
        change_pct = ((today_close - yest_close) / yest_close) * 100 if yest_close > 0 else 0
        cols[i].metric(label=name, value=f"{today_close:.2f}", delta=f"{change_pct:.2f}%")
    except:
        cols[i].metric(label=name, value="Error", delta=None)

st.markdown("---")

# --- 3. AUTO-SCAN & MANUAL SCAN LOGIC ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Scan Settings")

# Query params se state maintain karna (taaki refresh ke baad setting na ude)
params = st.query_params
default_auto = True if params.get("auto") == "true" else False

auto_refresh = st.sidebar.checkbox("⏰ Auto-Scan Mode (Har 1 ghante mein chalega)", value=default_auto)

start_scan = False

if auto_refresh:
    st.query_params["auto"] = "true"
    # JS Meta tag jo page ko har 3600 second (1 hour) mein refresh karega
    st.markdown("<meta http-equiv='refresh' content='3600'>", unsafe_allow_html=True)
    st.info("⏰ Auto-Scan Mode ON: Tool khud har 1 ghante mein scan karke Telegram alert bhejega. (Browser tab khula rakhein)")
    start_scan = True  # Page load hote hi khud scan chalu ho jayega
else:
    if "auto" in st.query_params:
        del st.query_params["auto"]
    # Agar Auto-mode band hai, toh normal Manual button dikhega
    start_scan = st.button("🔄 Start Market Scan (Manual)")

# --- MARKET SCANNER ---
if start_scan:
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            stocks = f.read().splitlines()
        
        st.info(f"📂 Analyzing {len(stocks)} stocks... Please wait.")
        progress_bar = st.progress(0)
        results = []
        
        for i, s in enumerate(stocks):
            s = s.strip()
            if s:
                ticker = s if s.endswith(".NS") else f"{s}.NS"
                res = analyze_stock(ticker)
                if res: results.append(res)
            
            progress_bar.progress((i + 1) / len(stocks))
            # time.sleep(0.05) # No need for sleep on single downloads if API limits allow, keep off for performance
        
        if results:
            df_results = pd.DataFrame(results)
            st.subheader("📈 Trading Signals (Live)")
            
            # --- APPLY STYLING HERE before displaying ---
            # Apply color style function specifically to SIGNAL column cells
            styled_df = df_results.style.applymap(color_signal, subset=['SIGNAL'])
            
            # Pass the STYLED dataframe to Streamlit
            st.dataframe(styled_df, use_container_width=True)
            
            st.success("✅ Analysis Complete!")
        else:
            st.warning("⚠️ Koi valid data nahi mila. Watchlist check karein.")
    except FileNotFoundError:
        st.error(f"❌ '{WATCHLIST_FILE}' file nahi mili! Dhyan rahe ye GitHub repo me ho.")
