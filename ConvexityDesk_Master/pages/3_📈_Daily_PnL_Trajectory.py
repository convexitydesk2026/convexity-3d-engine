import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import datetime

st.set_page_config(page_title="Daily PnL Trajectory | Convexity Desk", layout="wide")

st.markdown("""
    <style>
        .mobile-blocker { display: none; }
        @media (max-width: 768px) { 
            .stApp > header { display: none !important; }
            section.main > div.block-container { display: none !important; }
            .mobile-blocker { 
                display: flex !important; flex-direction: column; justify-content: center; align-items: center; 
                height: 100vh; width: 100vw; background-color: #0e1117; color: white; text-align: center; 
                padding: 40px; position: fixed; top: 0; left: 0; z-index: 999999; 
            }
        }
    </style>
    <div class="mobile-blocker">
        <h1 style="font-size: 24px; color: #ff4b4b; margin-bottom: 20px;">Desktop Only</h1>
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

st.warning("⚠️ Website under development. Do not rely on the results. Come back in one week. If you still see this header it means we are NOT yet ready for public use.")

st.title("Daily PnL Trajectory")
st.markdown("Replicate and analyze institutional equity curve trajectories.")

st.markdown("---")
st.markdown("### Upload Custom Portfolio CSV")
st.markdown("To visualize your own trajectory, upload a CSV matching the exact columns of the dummy template below. If no file is uploaded, the app will generate 1 year of synthetic dummy data.")
uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
st.markdown("---")

@st.cache_data(ttl=3600)

def generate_dummy_data():
    # Download 252 days of benchmark data
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)
    
    spy = yf.download("SPY", start=start_date, end=end_date, progress=False)['Close']
    qqq = yf.download("QQQ", start=start_date, end=end_date, progress=False)['Close']
    rsp = yf.download("RSP", start=start_date, end=end_date, progress=False)['Close']
    
    # Align dates and flatten arrays to fix yfinance 2D array bug
    df = pd.DataFrame({'date': spy.index, 'spy': np.array(spy).flatten(), 'qqq': np.array(qqq).flatten(), 'rsp': np.array(rsp).flatten()})
    df['spy_cum'] = (df['spy'] / df['spy'].iloc[0]) - 1
    df['qqq_cum'] = (df['qqq'] / df['qqq'].iloc[0]) - 1
    df['rsp_cum'] = (df['rsp'] / df['rsp'].iloc[0]) - 1
    
    # Generate Dummy Silo PnL
    np.random.seed(42)
    days = len(df)
    
    # Silo A (Conservative, steady positive drift)
    df['silo_a_pnl'] = np.random.normal(loc=150, scale=300, size=days)
    
    # Silo C (Aggressive, higher volatility)
    df['silo_c_pnl'] = np.random.normal(loc=250, scale=800, size=days)
    
    # Silo D (Hedge, slightly negative drift but spikes on down days)
    df['silo_d_pnl'] = np.random.normal(loc=-50, scale=200, size=days)
    # Add artificial spikes when SPY drops
    spy_returns = df['spy'].pct_change().fillna(0)
    df.loc[spy_returns < -0.01, 'silo_d_pnl'] += np.random.uniform(1000, 3000, size=(spy_returns < -0.01).sum())

    df['daily_pnl'] = df['silo_a_pnl'] + df['silo_c_pnl'] + df['silo_d_pnl']
    df['cum_pnl'] = df['daily_pnl'].cumsum()
    
    # Generate Dummy Alpha Gear & Options Trend
    df['alpha_gear'] = np.random.choice([0, 1, 2, 3, 4, 5], size=days, p=[0.05, 0.1, 0.15, 0.2, 0.3, 0.2])
    # Smooth the gear somewhat so it's not jumping every day
    df['alpha_gear'] = df['alpha_gear'].rolling(window=5, min_periods=1).median().astype(int)
    
    df['opt_dir'] = np.where(spy_returns > 0, 'Bull', 'Bear')
    
    return df

if uploaded_file is not None:
    # Process uploaded CSV
    df = pd.read_csv(uploaded_file)
    df['date'] = pd.to_datetime(df['Date'])
    df['silo_a_pnl'] = df.get('Silo A Daily PnL', 0)
    df['silo_c_pnl'] = df.get('Silo C Daily PnL', 0)
    df['silo_d_pnl'] = df.get('Silo D Daily PnL', 0)
    df['alpha_gear'] = df.get('Alpha Gear (0-5)', 0)
    df['opt_dir'] = df.get('Options Trend', 'Bull')
    
    df['daily_pnl'] = df['silo_a_pnl'] + df['silo_c_pnl'] + df['silo_d_pnl']
    df['cum_pnl'] = df['daily_pnl'].cumsum()
    
    # We must fetch benchmarks for the date range provided in the CSV
    start_date = df['date'].min()
    end_date = df['date'].max()
    spy = yf.download("SPY", start=start_date, end=end_date + datetime.timedelta(days=1), progress=False)['Close']
    qqq = yf.download("QQQ", start=start_date, end=end_date + datetime.timedelta(days=1), progress=False)['Close']
    rsp = yf.download("RSP", start=start_date, end=end_date + datetime.timedelta(days=1), progress=False)['Close']
    
    bench_df = pd.DataFrame({'date': spy.index.tz_localize(None), 'spy': np.array(spy).flatten(), 'qqq': np.array(qqq).flatten(), 'rsp': np.array(rsp).flatten()})
    
    df = pd.merge_asof(df.sort_values('date'), bench_df.sort_values('date'), on='date')
    df['spy_cum'] = (df['spy'] / df['spy'].iloc[0]) - 1
    df['qqq_cum'] = (df['qqq'] / df['qqq'].iloc[0]) - 1
    df['rsp_cum'] = (df['rsp'] / df['rsp'].iloc[0]) - 1
else:
    df = generate_dummy_data()

# Calculate scaling for USD lines (Assume starting NAV of $100k)
initial_nav = 100000
df['spy_usd_cum'] = df['spy_cum'] * initial_nav
df['qqq_usd_cum'] = df['qqq_cum'] * initial_nav
df['rsp_usd_cum'] = df['rsp_cum'] * initial_nav
df['cum_return'] = df['cum_pnl'] / initial_nav

st.markdown("### Portfolio vs Benchmarks (1-Year Trajectory)")
privacy_mode = False

fig_pnl = go.Figure()

if not privacy_mode:
    # Add Silo Bars
    fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_d_pnl'], name='Silo D', marker_color='#c084fc'))
    fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_a_pnl'], name='Silo A', marker_color='#60a5fa'))
    fig_pnl.add_trace(go.Bar(x=df['date'], y=df['silo_c_pnl'], name='Silo C', marker_color='#4ade80'))
    
    # Add Cumulative Lines
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['cum_pnl'], name='Estate (Cum PnL USD)', mode='lines', line=dict(color='black', width=6), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['spy_usd_cum'], name='SPY (Cum PnL USD)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['qqq_usd_cum'], name='QQQ (Cum PnL USD)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['rsp_usd_cum'], name='RSP (Cum PnL USD)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))
else:
    # Pure Percentages in Privacy Mode
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['spy_cum']*100, name='SPY (Cum Return %)', mode='lines', line=dict(color='#3b82f6', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['qqq_cum']*100, name='QQQ (Cum Return %)', mode='lines', line=dict(color='#dc2626', width=3), yaxis='y2'))
    fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['rsp_cum']*100, name='RSP (Cum Return %)', mode='lines', line=dict(color='#16a34a', width=3), yaxis='y2'))

# Formatting for Alpha Gear and Options Engine
df['alpha_bg'] = df['alpha_gear'].map({5: '#14532d', 4: '#22c55e', 3: '#84cc16', 2: '#eab308', 1: '#f97316', 0: '#991b1b'})
df['alpha_txt'] = df['alpha_gear'].map({5: 'white', 4: 'black', 3: 'black', 2: 'black', 1: 'black', 0: 'white'})
df['opt_bg'] = df['opt_dir'].map({'Bull': '#166534', 'Bear': '#991b1b'})

# Alpha Engine (Squares)
fig_pnl.add_trace(go.Scatter(
    x=df['date'], y=[0]*len(df), mode='markers+text', 
    marker=dict(color=df['alpha_bg'], symbol='square', size=16, line=dict(width=1, color='black')),
    text=df['alpha_gear'], textposition='middle center', textfont=dict(color=df['alpha_txt'], size=10, weight='bold'),
    hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Alpha Gear:</b> %{customdata}<extra></extra>",
    customdata=df['alpha_gear'], 
    name='Alpha Engine', showlegend=False, yaxis='y3'
))

# Options Engine (Circles) - Hidden in Privacy Mode
if not privacy_mode:
    fig_pnl.add_trace(go.Scatter(
        x=df['date'], y=[-1]*len(df), mode='markers', 
        marker=dict(color=df['opt_bg'], symbol='circle', size=12, line=dict(width=1, color='black')),
        hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br><b>Options Trend:</b> %{customdata}<extra></extra>",
        customdata=df['opt_dir'], 
        name='Options Engine', showlegend=False, yaxis='y3'
    ))

last_dt = df['date'].iloc[-1]

if not privacy_mode:
    est_val = df['cum_pnl'].iloc[-1]
    spy_val = df['spy_usd_cum'].iloc[-1]
    qqq_val = df['qqq_usd_cum'].iloc[-1]
    rsp_val = df['rsp_usd_cum'].iloc[-1]
    
    est_pct = df['cum_return'].iloc[-1] * 100
    spy_pct = df['spy_cum'].iloc[-1] * 100
    qqq_pct = df['qqq_cum'].iloc[-1] * 100
    rsp_pct = df['rsp_cum'].iloc[-1] * 100
    
    fig_pnl.add_annotation(x=last_dt, y=est_val, text=f"{est_pct:.1f}%<br>${est_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='black', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=spy_val, text=f"{spy_pct:.1f}%<br>${spy_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#3b82f6', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=qqq_val, text=f"{qqq_pct:.1f}%<br>${qqq_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#dc2626', font=dict(color='white', size=11))
    fig_pnl.add_annotation(x=last_dt, y=rsp_val, text=f"{rsp_pct:.1f}%<br>${rsp_val:,.0f}", showarrow=False, xanchor='left', yref='y2', bgcolor='#16a34a', font=dict(color='white', size=11))

fig_pnl.update_layout(
    height=600,
    margin=dict(l=0, r=40, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title='Daily PnL (USD)', side='left', showgrid=False, zeroline=True, zerolinecolor='lightgrey', domain=[0.1, 1]),
    yaxis2=dict(title='Cumulative PnL (USD)' if not privacy_mode else 'Cumulative Return (%)', side='right', overlaying='y', showgrid=True, gridcolor='#f1f5f9', zeroline=False),
    yaxis3=dict(domain=[0, 0.08], showgrid=False, zeroline=False, showticklabels=False),
    barmode='relative',
    plot_bgcolor='white',
    paper_bgcolor='white'
)

st.plotly_chart(fig_pnl, use_container_width=True)

st.markdown("---")
st.markdown("### Dummy Data Ledger Template")
st.markdown("This is the exact CSV schema required to render the chart above. You can download this template, replace it with your own historical PnL, and upload it at the top of the page.")

display_df = df[['date', 'silo_a_pnl', 'silo_c_pnl', 'silo_d_pnl', 'alpha_gear', 'opt_dir']].copy()
display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
display_df = display_df.rename(columns={
    'date': 'Date', 'silo_a_pnl': 'Silo A Daily PnL', 'silo_c_pnl': 'Silo C Daily PnL',
    'silo_d_pnl': 'Silo D Daily PnL', 'alpha_gear': 'Alpha Gear (0-5)', 'opt_dir': 'Options Trend'
})
st.dataframe(display_df.tail(10), use_container_width=True)
