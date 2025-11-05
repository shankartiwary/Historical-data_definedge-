import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import time

st.title('Financial Data Dashboard')

st.sidebar.header('User Input')
api_token = st.sidebar.text_input('API Token', type='password')
api_secret = st.sidebar.text_input('API Secret', type='password')

connection_status_placeholder = st.sidebar.empty()

def check_broker_connection(token, secret):
    """Simulates a broker connection check."""
    if token and secret:
        time.sleep(1)
        return True
    return False

def get_nifty50_historical_data():
    """Placeholder for fetching Nifty 50 historical data."""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=30)
    dates = pd.to_datetime(pd.date_range(start=start_date, end=end_date, freq='D'))
    prices = pd.Series(range(len(dates))) + 17000 + (pd.Series(range(len(dates))).cumsum())

    data = {'date': dates, 'price': prices}
    return pd.DataFrame(data)

def get_option_chain(symbol, expiry_date):
    """Placeholder for fetching option chain data."""
    dummy_data = {
        'strike': [17000, 17100, 17200, 17300, 17400, 17500],
        'ce_oi': [100000, 120000, 150000, 130000, 110000, 90000],
        'pe_oi': [90000, 110000, 140000, 160000, 120000, 100000],
        'ce_volume': [50000, 60000, 75000, 65000, 55000, 45000],
        'pe_volume': [45000, 55000, 70000, 80000, 60000, 50000],
    }
    return pd.DataFrame(dummy_data)

if api_token and api_secret:
    if check_broker_connection(api_token, api_secret):
        connection_status_placeholder.success("🟢 Connected to Broker")

        tab1, tab2 = st.tabs(["Nifty 50", "Options Chain"])

        with tab1:
            st.header('Nifty 50 Historical Data (Last 30 Days)')
            nifty_data = get_nifty50_historical_data()
            st.dataframe(nifty_data)

            fig_nifty = go.Figure()
            fig_nifty.add_trace(go.Scatter(x=nifty_data['date'], y=nifty_data['price'], mode='lines', name='Nifty 50'))
            fig_nifty.update_layout(xaxis_title='Date', yaxis_title='Price')
            st.plotly_chart(fig_nifty)

        with tab2:
            st.sidebar.header('Options Chain')
            symbol = st.sidebar.text_input('Symbol', 'NIFTY')
            expiry_date = st.sidebar.date_input('Expiry Date', value=datetime.today())

            if symbol and expiry_date:
                try:
                    df = get_option_chain(symbol, expiry_date.strftime('%Y-%m-%d'))

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

                except Exception as e:
                    st.error(f"An error occurred: {e}")
    else:
        connection_status_placeholder.error("🔴 Disconnected")
else:
    connection_status_placeholder.info("🟡 Enter API credentials to connect.")
