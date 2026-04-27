import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

# --- PAGE SETUP ---
st.set_page_config(page_title="Hina Swing Trade AI", layout="wide")

# --- SECRETS (Telegram Credentials) ---
try:
    # .strip() lagaya hai taaki koi galti se space aa jaye toh wo hat jaye
    BOT_TOKEN = str(st.secrets["BOT_TOKEN"]).strip()
    CHAT_ID = str(st.secrets["CHAT_ID"]).strip()
except:
    st.warning("⚠️ Security Alert: Streamlit Secrets mein Telegram Token aur Chat ID set nahi hain.")
    st.stop()

WATCHLIST_FILE = "HinaSwingTrade.txt"

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

if 'notepad_text' not in st.session_state:
    st.session_state['notepad_text'] = ""

notes = st.sidebar.text_area("Yahan notes likhein (Niche se khinch kar bada karein):", value=st.session_state['notepad_text'], height=250)
st.session_state['notepad_text'] = notes

# --- SECTOR INDICES (Nifty 50 Added) ---
SECTORS = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "NIFTY BANK",
    "^CNXFMCG": "NIFTY FMCG",
    "^CNXIT": "NIFTY IT",
    "^CNXMETAL": "NIFTY METAL",
    "^CNXPHARMA": "NIFTY PHARMA",
    "^CNXPSUBANK": "NIFTY PSU"
}

def send_telegram_msg(message):
    """Fixed Telegram Notification Logic"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try: 
        # Using json=payload ensures proper format processing by Telegram
        requests.post(url, json=payload, timeout=10)
    except Exception as e: 
        pass

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

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 75: return None

        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_75'] = df['Close'].ewm(span=75, adjust=False).mean()
        df['Vol_Avg_15'] = df['Volume'].rolling(window=15).mean()
        df['Support_15d'] = df['Low'].rolling(window=15).min()
        df['Resist_15d'] = df['High'].rolling(window=15).max()

        close = float(df['Close'].iloc[-1].iloc[0] if isinstance(df['Close'].iloc[-1], pd.Series) else df['Close'].iloc[-1])
        e9 = float(df['EMA_9'].iloc[-1].iloc[0] if isinstance(df['EMA_9'].iloc[-1], pd.Series) else df['EMA_9'].iloc[-1])
        e20 = float(df['EMA_20'].iloc[-1].iloc[0] if isinstance(df['EMA_20'].iloc[-1], pd.Series) else df['EMA_20'].iloc[-1])
        e75 = float(df['EMA_75'].iloc[-1].iloc[0] if isinstance(df['EMA_75'].iloc[-1], pd.Series) else df['EMA_75'].iloc[-1])
        
        vol_today = float(df['Volume'].iloc[-1].iloc[0] if isinstance(df['Volume'].iloc[-1], pd.Series) else df['Volume'].iloc[-1])
        vol_avg = float(df['Vol_Avg_15'].iloc[-1].iloc[0] if isinstance(df['Vol_Avg_15'].iloc[-1], pd.Series) else df['Vol_Avg_15'].iloc[-1])
        vol_x = (vol_today / vol_avg) if vol_avg > 0 else 0
        
        supp = float(df['Support_15d'].iloc[-1].iloc[0] if isinstance(df['Support_15d'].iloc[-1], pd.Series) else df['Support_15d'].iloc[-1])
        res = float(df['Resist_15d'].iloc[-1].iloc[0] if isinstance(df['Resist_15d'].iloc[-1], pd.Series) else df['Resist_15d'].iloc[-1])
        
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

# --- Custom Styling Function for Pandas ---
def highlight_signal(val):
    """Background Color Logic"""
    if isinstance(val, str):
        if 'BUY' in val:
            return 'background-color: #A9DFBF; color: black; font-weight: bold;' # Light Green
        elif 'SELL' in val:
            return 'background-color: #F5B7B1; color: black; font-weight: bold;' # Light Red
        elif 'HOLD' in val:
            return 'background-color: #E5E7E9; color: black; font-weight: bold;' # Light Gray
    return ''

# --- MAIN DASHBOARD ---
st.title("🚀 Hina Swing Trade - AI Terminal")

st.markdown("---")
st.subheader("📊 Sectoral Indices Heatmap (Live)")

tickers = list(SECTORS.keys())
data = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
cols = st.columns(len(SECTORS)) # Automatically creates equal columns in a line

for i, (ticker, name) in enumerate(SECTORS.items()):
    try:
        today_close = float(data[ticker].iloc[-1].iloc[0] if isinstance(data[ticker].iloc[-1], pd.Series) else data[ticker].iloc[-1])
        yest_close = float(data[ticker].iloc[-2].iloc[0] if isinstance(data[ticker].iloc[-2], pd.Series) else data[ticker].iloc[-2])
        change_pct = ((today_close - yest_close) / yest_close) * 100
        cols[i].metric(label=name, value=f"{today_close:.2f}", delta=f"{change_pct:.2f}%")
    except:
        cols[i].metric(label=name, value="Error", delta=None)

st.markdown("---")

# --- AUTO-SCAN & MANUAL SCAN LOGIC ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Scan Settings")

params = st.query_params
default_auto = True if params.get("auto") == "true" else False

auto_refresh = st.sidebar.checkbox("⏰ Auto-Scan Mode (Har 1 ghante mein chalega)", value=default_auto)

start_scan = False

if auto_refresh:
    st.query_params["auto"] = "true"
    st.markdown("<meta http-equiv='refresh' content='3600'>", unsafe_allow_html=True)
    st.info("⏰ Auto-Scan Mode ON: Tool khud har 1 ghante mein scan karke Telegram alert bhejega. (Browser tab khula rakhein)")
    start_scan = True 
else:
    if "auto" in st.query_params:
        del st.query_params["auto"]
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
            time.sleep(0.05) 
        
        if results:
            df_results = pd.DataFrame(results)
            
            # --- SORTING LOGIC: BUY on Top ---
            def get_sort_value(signal):
                if 'BUY' in signal: return 0
                elif 'HOLD' in signal: return 1
                elif 'SELL' in signal: return 2
                return 3
            
            df_results['sort_order'] = df_results['SIGNAL'].apply(get_sort_value)
            df_results = df_results.sort_values(by='sort_order').drop(columns=['sort_order']).reset_index(drop=True)
            
            # --- APPLYING COLORS ---
            try:
                styled_df = df_results.style.map(highlight_signal, subset=['SIGNAL'])
            except AttributeError:
                # Fallback for older Pandas versions
                styled_df = df_results.style.applymap(highlight_signal, subset=['SIGNAL'])
                
            st.subheader("📈 Trading Signals (Live)")
            st.dataframe(styled_df, use_container_width=True)
            st.success("✅ Analysis Complete!")
        else:
            st.warning("⚠️ Koi valid data nahi mila. Watchlist check karein.")
    except FileNotFoundError:
        st.error(f"❌ '{WATCHLIST_FILE}' file nahi mili! Dhyan rahe ye GitHub repo me ho.")
