import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import numpy as np
# --- STRATEGY 2 NEW IMPORTS ---
import pandas_ta as ta
import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="Hina Swing Trade AI", layout="wide")

# --- SECRETS (Telegram) ---
try:
    BOT_TOKEN = st.secrets["BOT_TOKEN"]
    CHAT_ID = st.secrets["CHAT_ID"]
except:
    st.warning("⚠️ Security Alert: Streamlit Secrets mein Telegram Token aur Chat ID set nahi hain.")
    st.stop()

WATCHLIST_FILE = "HinaSwingTrade.txt"

# --- HELPER FUNCTIONS FOR ROBUST DATA ACCESS ---
def get_safe_series(df, col_name):
    try:
        if col_name in df.columns:
            return df[col_name]
        if isinstance(df.columns, pd.MultiIndex):
            if df.columns.nlevels > 1:
                return df.xs(col_name, level=0, axis=1)
        if col_name in df.columns.get_level_values(0):
            return df[col_name]
    except Exception as e:
        pass
    return pd.Series(dtype=float)

def get_latest_float(series):
    try:
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        if series.empty:
            return np.nan
        val = series.iloc[-1]
        if isinstance(val, pd.Series):
             return float(val.iloc[0])
        else:
             return float(val)
    except Exception as e:
        return np.nan 

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

# --- SECTOR INDICES ---
SECTORS = {
    "^NSEBANK": "NIFTY BANK",
    "^NSENIFTY": "NIFTY 50",
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

# --- 4. SIGNAL STYLING FUNCTION (Original) ---
def color_signal(val):
    background_style = ''
    text_style = ''
    
    if val == '✅ BUY':
        background_style = 'background-color: rgba(30, 255, 30, 0.6);' 
        text_style = 'color: white;' 
    elif val == '❌ SELL':
        background_style = 'background-color: rgba(255, 30, 30, 0.6);' 
        text_style = 'color: white;' 
    elif val == '⏳ HOLD':
        background_style = 'background-color: rgba(255, 165, 0, 0.15);' 
        text_style = 'color: #FFA500;' 
        
    return f"{background_style} {text_style}"

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 75: return None

        close_series = get_safe_series(df, 'Close')
        volume_series = get_safe_series(df, 'Volume')
        low_series = get_safe_series(df, 'Low')
        high_series = get_safe_series(df, 'High')

        ema9_series = close_series.ewm(span=9, adjust=False).mean()
        ema20_series = close_series.ewm(span=20, adjust=False).mean()
        ema75_series = close_series.ewm(span=75, adjust=False).mean()
        vol_avg_series = volume_series.rolling(window=15).mean()
        supp_series = low_series.rolling(window=15).min()
        res_series = high_series.rolling(window=15).max()

        close = get_latest_float(close_series)
        e9 = get_latest_float(ema9_series)
        e20 = get_latest_float(ema20_series)
        e75 = get_latest_float(ema75_series)
        
        vol_today = get_latest_float(volume_series)
        vol_avg = get_latest_float(vol_avg_series)
        
        if np.isnan(close) or np.isnan(e20) or np.isnan(e75):
            return None 
            
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

# ==============================================================================
# --- NEW: STRATEGY 2 HELPER FUNCTIONS (50 & 200 EMA CROSSOVER) ---
# ==============================================================================
def analyze_stock_ema(symbol, timeframe):
    try:
        if timeframe == "1 Day":
            interval = "1d"
            period = "6mo"
        else:
            interval = "1h"
            period = "730d"

        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period=period, interval=interval)
        
        if df.empty or len(df) < 200:
            return None
            
        if timeframe == "4 Hrs":
            df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['RSI_MA'] = ta.sma(df['RSI'], length=14)
        
        df.ta.vwap(append=True)
        vwap_col = [col for col in df.columns if 'VWAP' in col][0]

        df = df.dropna()
        if len(df) < 6: 
            return None

        recent_data = df.tail(6)
        crossover_happened = False
        for i in range(1, len(recent_data)):
            prev = recent_data.iloc[i-1]
            curr = recent_data.iloc[i]
            if prev['EMA_50'] <= prev['EMA_200'] and curr['EMA_50'] > curr['EMA_200']:
                crossover_happened = True
                break

        current_candle = df.iloc[-1]
        is_currently_bullish = current_candle['EMA_50'] > current_candle['EMA_200']

        if crossover_happened and is_currently_bullish:
            last_30_days = df.tail(30)
            avg_volume = last_30_days['Volume'].mean()
            current_volume = current_candle['Volume']
            vol_multiplier = current_volume / avg_volume if avg_volume > 0 else 0
            vol_text = f"{vol_multiplier:.1f}x Avg"

            sector = ticker.info.get('sector', 'Unknown')

            return {
                "Sector": sector,
                "Current Price": round(current_candle['Close'], 2),
                "50 EMA": round(current_candle['EMA_50'], 2),
                "200 EMA": round(current_candle['EMA_200'], 2),
                "RSI": round(current_candle['RSI'], 2),
                "RSI MA": round(current_candle['RSI_MA'], 2),
                "VWAP": round(current_candle[vwap_col], 2),
                "Volume": vol_text,
                "Action": "BUY"
            }
    except Exception as e:
        return None
    return None

def load_watchlist_ema(filename="pinshutrade.txt"):
    try:
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        st.error(f"Error: '{filename}' file nahi mili. Dhyan rahe ye GitHub repo me ho.")
        return []

def highlight_table_ema(val):
    if val == "BUY":
        return 'background-color: rgba(0, 255, 0, 0.3); color: white; font-weight: bold'
    elif isinstance(val, (int, float)):
         return 'color: #D3D3D3;'
    return ''
# ==============================================================================


# --- MAIN DASHBOARD (COMBINED WITH TABS) ---
st.title("🚀 Hina Swing Trade - AI Terminal")

# Creating Tabs for both strategies
tab1, tab2 = st.tabs(["🚀 Hina Swing Strategy (Original)", "📈 50 & 200 EMA Crossover (Pinshu)"])


# --- TAB 1: ORIGINAL HINA STRATEGY ---
with tab1:
    st.markdown("---")
    st.subheader("📊 Sectoral Indices Heatmap (Live)")

    tickers = list(SECTORS.keys())
    data = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
    cols = st.columns(len(SECTORS))

    for i, (ticker, name) in enumerate(SECTORS.items()):
        try:
            ticker_data = data[ticker] if ticker in data.columns else None
            if ticker_data is not None and isinstance(ticker_data, pd.Series):
                 today_close = float(ticker_data.iloc[-1])
                 yest_close = float(ticker_data.iloc[-2])
            elif ticker_data is not None and isinstance(ticker_data, pd.DataFrame):
                 today_close = float(ticker_data.iloc[-1].iloc[0]) 
                 yest_close = float(ticker_data.iloc[-2].iloc[0])
            else:
                 cols[i].metric(label=name, value="Error", delta=None)
                 continue
            
            change_pct = ((today_close - yest_close) / yest_close) * 100 if yest_close > 0 else 0
            cols[i].metric(label=name, value=f"{today_close:.2f}", delta=f"{change_pct:.2f}%")
        except:
            cols[i].metric(label=name, value="Error", delta=None)

    st.markdown("---")

    # --- AUTO-SCAN & MANUAL SCAN LOGIC (Original) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Scan Settings (Hina Strategy)")

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

    # --- MARKET SCANNER (Original) ---
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
            
            if results:
                df_results = pd.DataFrame(results)
                st.subheader("📈 Trading Signals (Live)")
                
                # --- SORTING LOGIC: BUY 1st, SELL 2nd, HOLD 3rd ---
                sort_order = {"✅ BUY": 1, "❌ SELL": 2, "⏳ HOLD": 3}
                df_results['Sort'] = df_results['SIGNAL'].map(sort_order)
                df_results = df_results.sort_values('Sort').drop('Sort', axis=1).reset_index(drop=True)
                
                # --- APPLY STYLING & PRECISION ---
                styled_df = df_results.style.format(precision=2).map(color_signal, subset=['SIGNAL'])
                st.dataframe(styled_df, use_container_width=True)
                
                st.success("✅ Analysis Complete!")
            else:
                st.warning("⚠️ Koi valid data nahi mila. Watchlist check karein.")
        except FileNotFoundError:
            st.error(f"❌ '{WATCHLIST_FILE}' file nahi mili! Dhyan rahe ye GitHub repo me ho.")


# --- TAB 2: NEW 50 & 200 EMA CROSSOVER STRATEGY ---
with tab2:
    st.markdown("---")
    st.subheader("📈 Strategy 2 Scanner: 50 & 200 EMA Crossover")
    
    col1, col2 = st.columns([1, 2])

    with col1:
        selected_timeframe = st.selectbox("Select Timeframe:", ["1 Day", "4 Hrs"], key="tf_ema_box")

    with col2:
        st.write("") 
        st.write("")
        with st.form(key='scan_form_ema'):
            start_scan_ema = st.form_submit_button(label='🚀 Start EMA Scanning')

    if start_scan_ema:
        watchlist_ema = load_watchlist_ema()
        
        if not watchlist_ema:
            st.warning("Watchlist empty hai ya read nahi ho payi. ('pinshutrade.txt' file check karein)")
        else:
            st.info(f"Scanning {len(watchlist_ema)} stocks on {selected_timeframe} timeframe... (1 sec per stock delay applied)")
            progress_bar_ema = st.progress(0)
            status_text_ema = st.empty()
            
            signals_ema = []
            serial_no = 1
            
            for i, symbol in enumerate(watchlist_ema):
                status_text_ema.text(f"Scanning: {symbol} ({i+1}/{len(watchlist_ema)})")
                
                result = analyze_stock_ema(symbol, selected_timeframe)
                
                if result:
                    final_row = {"S.No": serial_no, "Stock Name": symbol}
                    final_row.update(result)
                    signals_ema.append(final_row)
                    serial_no += 1
                    
                time.sleep(1)
                progress_bar_ema.progress((i + 1) / len(watchlist_ema))
                
            status_text_ema.text("Scanning Complete! ✅")
            
            if signals_ema:
                df_results_ema = pd.DataFrame(signals_ema)
                st.success(f"🎉 Found {len(df_results_ema)} stocks with a BUY signal!")
                
                styled_df_ema = df_results_ema.style.map(highlight_table_ema)
                st.dataframe(styled_df_ema, use_container_width=True, hide_index=True)
                
                csv_ema = df_results_ema.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv_ema,
                    file_name=f'EMA_Swing_Signals_{datetime.date.today()}.csv',
                    mime='text/csv',
                    key='dl_ema_btn'
                )
            else:
                st.warning("Koi aaisa stock nahi mila jisme last 5 din me 50 & 200 EMA crossover hua ho.")
