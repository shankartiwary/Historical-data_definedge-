import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from integrate import ConnectToIntegrate, IntegrateData
import requests
import zipfile
import io
from hashlib import sha256

st.title('Financial Data Dashboard')

# --- Session State Initialization ---
st.session_state.setdefault('connected', False)
st.session_state.setdefault('master_file', None)
st.session_state.setdefault('api_session_key', None)
st.session_state.setdefault('conn', None)
st.session_state.setdefault('login_initiated', False)
st.session_state.setdefault('otp_token', None)

# --- UI for Login Flow ---
st.sidebar.header('User Input')

if not st.session_state.login_initiated:
    api_token_input = st.sidebar.text_input('API Token', type='password')
    api_secret_input = st.sidebar.text_input('API Secret', type='password')
    initiate_button = st.sidebar.button('Get OTP')
else:
    otp_input = st.sidebar.text_input('Enter OTP', type='password')
    verify_button = st.sidebar.button('Verify OTP & Login')

connection_status_placeholder = st.sidebar.empty()

# --- Reusable Functions ---
@st.cache_data
def download_and_process_master_file():
    url = "https://app.definedgesecurities.com/public/nsefno.zip"
    response = requests.get(url)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            df = pd.read_csv(f, header=None)
            df.columns = ['SEGMENT', 'TOKEN', 'SYMBOL', 'TRADINGSYM', 'INSTRUMENT TYPE', 'EXPIRY', 'TICKSIZE', 'LOTSIZE', 'OPTIONTYPE', 'STRIKE', 'PRICEPREC', 'MULTIPLIER', 'ISIN', 'PRICEMULT', 'COMPANY']
            return df

def get_nifty50_historical_data(master_df, session_key):
    nifty_instrument = master_df[(master_df['SYMBOL'] == 'NIFTY') & (master_df['INSTRUMENT TYPE'] == 'FUTIDX')].iloc[0]
    token = nifty_instrument['TOKEN']
    to_date, from_date = datetime.today(), datetime.today() - timedelta(days=30)
    url = f"https://data.definedgesecurities.com/sds/history/NFO/{token}/day/{from_date.strftime('%d%m%Y%H%M')}/{to_date.strftime('%d%m%Y%H%M')}"
    response = requests.get(url, headers={'Authorization': session_key})
    response.raise_for_status()
    df = pd.DataFrame([row.split(',') for row in response.text.strip().split('\n')], columns=['Dateandtime', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI'])
    df['Dateandtime'] = pd.to_datetime(df['Dateandtime'])
    return df

def get_option_chain(master_df, symbol, expiry_date, conn):
    expiry_str = expiry_date.strftime('%d%m%Y')
    options_df = master_df[(master_df['SYMBOL'] == symbol) & (master_df['EXPIRY'] == expiry_str) & (master_df['INSTRUMENT TYPE'] == 'OPTIDX')]
    ic = IntegrateData(conn)
    chain_data = []
    for _, row in options_df.iterrows():
        try:
            quote = ic.quotes(exchange='NFO', trading_symbol=row['TRADINGSYM'])
            if quote and 'data' in quote:
                chain_data.append({'strike': row['STRIKE'] / (row['MULTIPLIER'] * (10 ** row['PRICEPREC'])), 'type': row['OPTIONTYPE'], 'oi': quote['data'].get('oi', 0), 'volume': quote['data'].get('volume', 0)})
        except Exception:
            pass # Ignore errors for single strikes
    chain_df = pd.DataFrame(chain_data)
    ce_df = chain_df[chain_df['type'] == 'CE'].rename(columns={'oi': 'ce_oi', 'volume': 'ce_volume'})
    pe_df = chain_df[chain_df['type'] == 'PE'].rename(columns={'oi': 'pe_oi', 'volume': 'pe_volume'})
    return pd.merge(ce_df, pe_df, on='strike', how='outer').fillna(0)

# --- Two-Step Login Logic ---
def initiate_login(token, secret):
    try:
        login_url = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/"
        response = requests.get(f"{login_url}login/{token}", headers={"api_secret": secret})
        response.raise_for_status()
        st.session_state.otp_token = response.json()["otp_token"]
        st.session_state.login_initiated = True
        st.sidebar.info("OTP sent. Please enter it below.")
    except Exception as e:
        st.sidebar.error(f"Failed to get OTP: {e}")

def verify_otp_and_connect(otp, token, secret, otp_token):
    try:
        login_url = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/"
        ac = sha256(f"{otp_token}{otp}{secret}".encode("utf-8")).hexdigest()
        response = requests.post(f"{login_url}token", json={"otp_token": otp_token, "otp": otp, "ac": ac})
        response.raise_for_status()
        data = response.json()

        conn = ConnectToIntegrate()
        conn.set_session_keys(data["uid"], data["actid"], data["api_session_key"], data["susertoken"])

        st.session_state.conn = conn
        st.session_state.api_session_key = data["api_session_key"]
        st.session_state.connected = True
    except Exception as e:
        st.sidebar.error(f"Login failed: {e}")
        st.session_state.login_initiated = False # Reset to allow re-entry of credentials

# --- Button Click Handling ---
if initiate_button:
    if api_token_input and api_secret_input:
        with st.spinner("Requesting OTP..."):
            st.session_state.api_token = api_token_input # Store for later use
            st.session_state.api_secret = api_secret_input
            initiate_login(api_token_input, api_secret_input)
        st.rerun()
    else:
        st.sidebar.warning("Please enter API Token and Secret.")

if 'verify_button' in locals() and verify_button:
    if otp_input:
        with st.spinner("Verifying OTP and connecting..."):
            verify_otp_and_connect(otp_input, st.session_state.api_token, st.session_state.api_secret, st.session_state.otp_token)
            if st.session_state.connected:
                with st.spinner('Downloading master file...'):
                    st.session_state.master_file = download_and_process_master_file()
        st.rerun()
    else:
        st.sidebar.warning("Please enter the OTP.")

# --- Main Dashboard Logic ---
if st.session_state.connected:
    connection_status_placeholder.success("🟢 Connected to Broker")
    if st.session_state.master_file is not None:
        st.sidebar.success("Master file loaded.")
        tab1, tab2 = st.tabs(["Nifty 50", "Options Chain"])
        with tab1:
            st.header('Nifty 50 Historical Data (Last 30 Days)')
            try:
                nifty_data = get_nifty50_historical_data(st.session_state.master_file, st.session_state.api_session_key)
                st.dataframe(nifty_data)
                fig_nifty = go.Figure(go.Scatter(x=nifty_data['Dateandtime'], y=nifty_data['Close'], mode='lines', name='Nifty 50'))
                st.plotly_chart(fig_nifty)
            except Exception as e:
                st.error(f"Failed to fetch Nifty 50 data: {e}")

        with tab2:
            st.sidebar.header('Options Chain')
            symbol = st.sidebar.text_input('Symbol', 'NIFTY')
            expiry = st.sidebar.date_input('Expiry Date', value=datetime.today())
            if st.sidebar.button('Fetch Option Chain'):
                with st.spinner('Fetching option chain...'):
                    df = get_option_chain(st.session_state.master_file, symbol, expiry, st.session_state.conn)
                    if not df.empty:
                        st.header(f'Options Data for {symbol}')
                        fig_oi = go.Figure([go.Bar(x=df['strike'], y=df['ce_oi'], name='Call OI'), go.Bar(x=df['strike'], y=df['pe_oi'], name='Put OI')])
                        st.plotly_chart(fig_oi)
                        fig_vol = go.Figure([go.Bar(x=df['strike'], y=df['ce_volume'], name='Call Volume'), go.Bar(x=df['strike'], y=df['pe_volume'], name='Put Volume')])
                        st.plotly_chart(fig_vol)
                        fig_noodle = go.Figure([go.Scatter(x=df['strike'], y=df['ce_oi'], mode='lines+markers', name='Call OI'), go.Scatter(x=df['strike'], y=df['pe_oi'], mode='lines+markers', name='Put OI')])
                        st.plotly_chart(fig_noodle)
    else:
        st.sidebar.error("Failed to load master file.")
else:
    connection_status_placeholder.info("🟡 Enter credentials to begin.")
