import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import pyotp
import time
from SmartApi import SmartConnect

# --- PAGE SETUP ---
st.set_page_config(page_title="Hina Swing Trade AI", layout="wide")

# --- SECRETS (100% SECURE - GitHub par keys nahi dikhengi) ---
try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    CHAT_ID = st.secrets["CHAT_ID"]
    ANGEL_API_KEY = st.secrets["ANGEL_API_KEY"]
    CLIENT_ID = st.secrets["CLIENT_ID"]
    PIN = st.secrets["PIN"]
    TOTP_SEED = st.secrets["TOTP_SEED"]
except:
    st.warning("⚠️ Security Alert: Streamlit Secrets set nahi hain. Streamlit Dashboard me jaakar Secrets daalein.")
    st.stop()

WATCHLIST_FILE = "HinaSwingTrade.txt" # Tumhari .txt file ka naam

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

def smart_login():
    """Angel One Automatic Login using Secrets"""
    try:
        smartApi = SmartConnect(api_key=ANGEL_API_KEY)
        totp = pyotp.TOTP(TOTP_SEED).now()
        login_data = smartApi.generateSession(CLIENT_ID, PIN, totp)
        if login_data['status']: return True
        return False
    except: return False

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

# --- STREAMLIT DASHBOARD UI ---
st.title("🚀 Hina Swing Trade - AI Terminal")

# 1. Angel One Auto-Login check
with st.spinner("Connecting to Angel One (Smart API)..."):
    if smart_login(): 
        st.success("✅ Angel One API Connected Successfully!")
    else: 
        st.error("⚠️ Angel One Connection Failed! Please check your credentials in Streamlit Secrets.")

st.markdown("---")
st.subheader("📊 Sectoral Indices Heatmap (Live)")

# 2. Sector Heatmap display
tickers = list(SECTORS.keys())
data = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
cols = st.columns(len(SECTORS))

for i, (ticker, name) in enumerate(SECTORS.items()):
    try:
        today_close = float(data[ticker].iloc[-1].iloc[0] if isinstance(data[ticker].iloc[-1], pd.Series) else data[ticker].iloc[-1])
        yest_close = float(data[ticker].iloc[-2].iloc[0] if isinstance(data[ticker].iloc[-2], pd.Series) else data[ticker].iloc[-2])
        change_pct = ((today_close - yest_close) / yest_close) * 100
        cols[i].metric(label=name, value=f"{today_close:.2f}", delta=f"{change_pct:.2f}%")
    except:
        cols[i].metric(label=name, value="Error", delta=None)

st.markdown("---")

# 3. Market Scan Button & Table
if st.button("🔄 Start Market Scan (Triveni Strategy)"):
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            stocks = f.read().splitlines()
        
        st.info(f"📂 Analyzing {len(stocks)} stocks... Please wait.")
        
        progress_bar = st.progress(0)
        results = []
        
        for i, s in enumerate(stocks):
            s = s.strip()
            if s:
                # Stock code check
                ticker = s if s.endswith(".NS") else f"{s}.NS"
                res = analyze_stock(ticker)
                if res: results.append(res)
            
            # Progress bar update
            progress_bar.progress((i + 1) / len(stocks))
            time.sleep(0.05) 
        
        if results:
            df_results = pd.DataFrame(results)
            st.subheader("📈 Trading Signals (Live)")
            # Streamlit Interactive Table
            st.dataframe(df_results, use_container_width=True)
            st.success("✅ Analysis Complete!")
        else:
            st.warning("⚠️ Koi valid data nahi mila. Watchlist check karein.")
    except FileNotFoundError:
        st.error(f"❌ '{WATCHLIST_FILE}' file nahi mili! Dhyan rahe ye GitHub repo me ho.")