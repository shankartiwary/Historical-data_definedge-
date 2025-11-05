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

# Initialize session state
if 'conn' not in st.session_state:
    st.session_state.conn = None
if 'api_session_key' not in st.session_state:
    st.session_state.api_session_key = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'master_file' not in st.session_state:
    st.session_state.master_file = None

st.sidebar.header('User Input')
api_token = st.sidebar.text_input('API Token', type='password')
api_secret = st.sidebar.text_input('API Secret', type='password')
login_button = st.sidebar.button('Login')

connection_status_placeholder = st.sidebar.empty()

@st.cache_data
def download_and_process_master_file():
    """Downloads and processes the NSE FNO master file."""
    url = "https://app.definedgesecurities.com/public/nsefno.zip"
    response = requests.get(url)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        csv_filename = z.namelist()[0]
        with z.open(csv_filename) as f:
            df = pd.read_csv(f, header=None)
            df.columns = [
                'SEGMENT', 'TOKEN', 'SYMBOL', 'TRADINGSYM', 'INSTRUMENT TYPE',
                'EXPIRY', 'TICKSIZE', 'LOTSIZE', 'OPTIONTYPE', 'STRIKE',
                'PRICEPREC', 'MULTIPLIER', 'ISIN', 'PRICEMULT', 'COMPANY'
            ]
            return df

def get_nifty50_historical_data(master_df, session_key):
    """Fetches Nifty 50 historical data."""
    nifty_instrument = master_df[
        (master_df['SYMBOL'] == 'NIFTY') &
        (master_df['INSTRUMENT TYPE'] == 'FUTIDX')
    ].iloc[0]
    token = nifty_instrument['TOKEN']

    to_date = datetime.today()
    from_date = to_date - timedelta(days=30)

    url = f"https://data.definedgesecurities.com/sds/history/NFO/{token}/day/{from_date.strftime('%d%m%Y%H%M')}/{to_date.strftime('%d%m%Y%H%M')}"
    headers = {'Authorization': session_key}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.text.strip().split('\n')
    df = pd.DataFrame([row.split(',') for row in data])
    df.columns = ['Dateandtime', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI']
    df['Dateandtime'] = pd.to_datetime(df['Dateandtime'])
    return df

def get_option_chain(master_df, symbol, expiry_date, conn):
    """Fetches the option chain data."""
    expiry_str = expiry_date.strftime('%d%m%Y')
    options_df = master_df[
        (master_df['SYMBOL'] == symbol) &
        (master_df['EXPIRY'] == expiry_str) &
        (master_df['INSTRUMENT TYPE'] == 'OPTIDX')
    ]

    ic = IntegrateData(conn)

    chain_data = []
    errors = []
    for _, row in options_df.iterrows():
        try:
            quote = ic.quotes(exchange='NFO', trading_symbol=row['TRADINGSYM'])

            if quote and isinstance(quote, dict) and 'data' in quote and isinstance(quote['data'], dict):
                quote_data = quote['data']
                chain_data.append({
                    'strike': row['STRIKE'] / (row['MULTIPLIER'] * (10 ** row['PRICEPREC'])),
                    'type': row['OPTIONTYPE'],
                    'oi': quote_data.get('oi', 0),
                    'volume': quote_data.get('volume', 0),
                })
            else:
                errors.append(f"Unexpected quote structure for {row['TRADINGSYM']}: {quote}")

        except Exception as e:
            errors.append(f"Could not fetch quote for {row['TRADINGSYM']}: {e}")

    if errors:
        st.warning("Some option contracts could not be fetched. The chain may be incomplete.")
        with st.expander("Show Errors"):
            for error in errors:
                st.error(error)

    if not chain_data:
        st.warning("Could not fetch any option chain data.")
        return pd.DataFrame()

    chain_df = pd.DataFrame(chain_data)

    ce_df = chain_df[chain_df['type'] == 'CE'].rename(columns={'oi': 'ce_oi', 'volume': 'ce_volume'})
    pe_df = chain_df[chain_df['type'] == 'PE'].rename(columns={'oi': 'pe_oi', 'volume': 'pe_volume'})

    merged_df = pd.merge(ce_df, pe_df, on='strike', how='outer').fillna(0)
    return merged_df

def check_broker_connection(token, secret):
    """Establishes a real connection to the broker."""
    try:
        conn = ConnectToIntegrate()
        login_response = conn.login(api_token=token, api_secret=secret)
        st.session_state.conn = conn
        st.session_state.api_session_key = login_response['api_session_key']
        st.session_state.connected = True
        return True
    except Exception as e:
        st.session_state.connected = False
        st.sidebar.error(f"Login failed: {e}")
        return False

if login_button and api_token and api_secret:
    with st.spinner('Connecting...'):
        check_broker_connection(api_token, api_secret)
        if st.session_state.connected:
            with st.spinner('Downloading master file...'):
                st.session_state.master_file = download_and_process_master_file()

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
        st.sidebar.warning("Master file not yet loaded. Please log in again.")

else:
    connection_status_placeholder.info("🟡 Enter API credentials and click Login.")
