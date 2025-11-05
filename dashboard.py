import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from integrate import ConnectToIntegrate, IntegrateData
import requests
import zipfile
import io

st.title('Financial Data Dashboard')

# --- Session State Initialization ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'master_file' not in st.session_state:
    st.session_state.master_file = None
if 'api_session_key' not in st.session_state:
    st.session_state.api_session_key = None
if 'conn' not in st.session_state:
    st.session_state.conn = None

# --- UI for Credentials and OTP ---
st.sidebar.header('User Input')
api_token = st.sidebar.text_input('API Token', type='password')
api_secret = st.sidebar.text_input('API Secret', type='password')
otp = st.sidebar.text_input('Enter OTP / 2FA Code', type='password')
login_button = st.sidebar.button('Login')
connection_status_placeholder = st.sidebar.empty()

# --- Reusable Functions ---
@st.cache_data
def download_and_process_master_file():
    # ... (same as before) ...
    pass

def get_nifty50_historical_data(master_df, session_key):
    # ... (same as before) ...
    pass

def get_option_chain(master_df, symbol, expiry_date, conn):
    # ... (same as before) ...
    pass

def connect_to_broker(token, secret, totp):
    # ... (same as before) ...
    pass

# --- Login Logic ---
if login_button:
    if api_token and api_secret and otp:
        with st.spinner('Connecting...'):
            if connect_to_broker(api_token, api_secret, otp):
                with st.spinner('Downloading master file...'):
                    st.session_state.master_file = download_and_process_master_file()
    else:
        st.sidebar.warning("Please enter API Token, Secret, and OTP.")

# --- Main Dashboard Logic ---
if st.session_state.connected:
    connection_status_placeholder.success("🟢 Connected to Broker")
    if st.session_state.master_file is not None:
        st.sidebar.success("Master file loaded.")

        tab1, tab2 = st.tabs(["Nifty 50", "Options Chain"])

        with tab1:
            st.header('Nifty 50 Historical Data (Last 30 Days)')
            try:
                with st.spinner('Fetching Nifty 50 data...'):
                    nifty_data = get_nifty50_historical_data(st.session_state.master_file, st.session_state.api_session_key)
                    st.dataframe(nifty_data)

                    fig_nifty = go.Figure()
                    fig_nifty.add_trace(go.Scatter(x=nifty_data['Dateandtime'], y=nifty_data['Close'], mode='lines', name='Nifty 50'))
                    fig_nifty.update_layout(xaxis_title='Date', yaxis_title='Price')
                    st.plotly_chart(fig_nifty)
            except Exception as e:
                st.error(f"Failed to fetch Nifty 50 data: {e}")

        with tab2:
            st.sidebar.header('Options Chain')
            symbol = st.sidebar.text_input('Symbol', 'NIFTY')
            expiry_date = st.sidebar.date_input('Expiry Date', value=datetime.today())
            fetch_options_button = st.sidebar.button('Fetch Option Chain')

            if fetch_options_button:
                with st.spinner('Fetching option chain...'):
                    df = get_option_chain(st.session_state.master_file, symbol, expiry_date, st.session_state.conn)

                    if not df.empty:
                        st.header(f'Options Data for {symbol}')
                        # Open Interest Plot
                        st.subheader('Open Interest')
                        fig_oi = go.Figure()
                        fig_oi.add_trace(go.Bar(x=df['strike'], y=df['ce_oi'], name='Call OI'))
                        fig_oi.add_trace(go.Bar(x=df['strike'], y=df['pe_oi'], name='Put OI'))
                        fig_oi.update_layout(barmode='group', xaxis_title='Strike Price', yaxis_title='Open Interest')
                        st.plotly_chart(fig_oi)

                        # Volume Plot
                        st.subheader('Volume')
                        fig_vol = go.Figure()
                        fig_vol.add_trace(go.Bar(x=df['strike'], y=df['ce_volume'], name='Call Volume'))
                        fig_vol.add_trace(go.Bar(x=df['strike'], y=df['pe_volume'], name='Put Volume'))
                        fig_vol.update_layout(barmode='group', xaxis_title='Strike Price', yaxis_title='Volume')
                        st.plotly_chart(fig_vol)

                        # Noodle Chart (Strike Price vs. OI)
                        st.subheader('Noodle Chart for Strike Prices')
                        fig_noodle = go.Figure()
                        fig_noodle.add_trace(go.Scatter(x=df['strike'], y=df['ce_oi'], mode='lines+markers', name='Call OI'))
                        fig_noodle.add_trace(go.Scatter(x=df['strike'], y=df['pe_oi'], mode='lines+markers', name='Put OI'))
                        fig_noodle.update_layout(xaxis_title='Strike Price', yaxis_title='Open Interest')
                        st.plotly_chart(fig_noodle)
    else:
        st.sidebar.error("Failed to load master file. Cannot proceed.")
else:
    connection_status_placeholder.info("🟡 Enter credentials and click Login.")
