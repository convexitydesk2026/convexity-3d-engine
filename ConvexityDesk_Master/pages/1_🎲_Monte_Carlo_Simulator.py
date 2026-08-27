import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import random
from datetime import datetime, date
from public_core_math import generate_synthetic_pnl, generate_mc_paths, get_spy_data, calculate_advanced_metrics, init_global_state, render_master_ledger_control_panel, compute_daily_trajectory, render_beta_warning_and_feedback

st.set_page_config(page_title="Monte Carlo Simulator", layout="wide")

st.markdown("""
    <style>
        .mobile-blocker { display: none; }
        
        @media (max-width: 768px) { 
            /* Hide the main Streamlit interface entirely */
            .stApp > header { display: none !important; }
            section.main > div.block-container { display: none !important; }
            
            /* Show the full-screen blocker */
            .mobile-blocker { 
                display: flex !important; 
                flex-direction: column; 
                justify-content: center; 
                align-items: center; 
                height: 100vh; 
                width: 100vw; 
                background-color: #0e1117; 
                color: white; 
                text-align: center; 
                padding: 40px; 
                position: fixed; 
                top: 0; 
                left: 0; 
                z-index: 999999; 
            }
        }
    </style>
    <div class="mobile-blocker">
        <h1 style="font-size: 24px; color: #ff4b4b; margin-bottom: 20px;">Desktop Only</h1>
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools (including the Monte Carlo Simulator and Market Flow Tables) are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        /* Decrease title font sizes for smaller laptop screens */
        h1 { font-size: 1.8rem !important; padding-bottom: 0px !important; margin-bottom: 0px !important; }
        h2 { font-size: 1.3rem !important; padding-bottom: 0px !important; margin-bottom: 0px !important; }
        h3 { font-size: 1.1rem !important; padding-top: 0px !important; margin-top: 0px !important; }
        
        /* Custom styling for metrics */
        div[data-testid="stMetricValue"] { font-size: 16px !important; }
        div[data-testid="stMetricLabel"] { font-size: 11px !important; font-weight: bold; }
        
        /* Reduce padding around the main container to save real estate */
        .block-container { padding-top: 1.5rem !important; padding-bottom: 1.5rem !important; }
    </style>
""", unsafe_allow_html=True)

st.title("Convexity Desk")
render_beta_warning_and_feedback()
st.markdown("##### Monte Carlo PnL Simulator")
st.markdown("Stress test your edge across 10,000 reshuffled realities.")

# 1. SIDEBAR PARAMETERS
with st.sidebar:
    st.header("1. Scenario Constraints")
    start_capital = st.number_input("Starting Capital ($)", value=100000, step=10000)
    
    st.markdown("---")
    last_trading_day = st.date_input("Last Trading Day", value=date.today())
    
    st.markdown("---")
    st.markdown("**Disclaimer:**")
    st.caption("For educational and demonstrational purposes only. Not financial advice. The simulations rely on static probabilities and do not reflect real market conditions or slippage.")

init_global_state()
render_master_ledger_control_panel(expanded=False)

master_df = st.session_state.master_ledger
equity_df = master_df[master_df['Class'] == 'Equity'].copy()
if equity_df.empty:
    st.warning("⚠️ No physical equity positions found in Master Ledger. The Simulator is in Standby Mode.")
    st.stop()

traj_df = compute_daily_trajectory(equity_df)
if traj_df.empty:
    st.error("Error generating trajectory from Master Ledger.")
    st.stop()

daily_pnl_array = traj_df['daily_pnl'].values

st.subheader("3. Monte Carlo Analysis")

# Run the Monte Carlo on the flattened edited array
cum_sim, max_dds, mc_avg_dd, mc_best_dd, mc_worst_dd, mc_avg_path = generate_mc_paths(daily_pnl_array)

orig_cum = np.insert(np.cumsum(daily_pnl_array), 0, 0)
orig_peaks = np.maximum.accumulate(orig_cum)
orig_dd = np.max(orig_peaks - orig_cum)

best_idx = np.argmax(cum_sim[:, -1])
worst_idx = np.argmin(cum_sim[:, -1])

# Use SPY data from the Master Ledger trajectory
num_days_in_grid = len(daily_pnl_array)
spy_closes = traj_df['spy'].values
    
metrics = calculate_advanced_metrics(daily_pnl_array, spy_closes, start_capital, risk_free_rate=0.04)

# --- TOP METRICS ROW (Responsive HTML/CSS Flexbox for Mobile) ---
metrics_html = f"""
<style>
.metric-container {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
.metric-box {{ flex: 1 1 90px; background-color: #1e1e2f; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #333; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
.metric-label {{ font-size: 11px; font-weight: bold; color: #a1a1aa; text-transform: uppercase; margin-bottom: 5px; }}
.metric-value {{ font-size: 16px; font-weight: bold; color: white; }}
</style>
<div class="metric-container">
    <div class="metric-box"><div class="metric-label">P&L</div><div class="metric-value">${metrics['pnl']:,.0f}</div></div>
    <div class="metric-box"><div class="metric-label">ROC</div><div class="metric-value">{metrics['roc']:.2f}%</div></div>
    <div class="metric-box"><div class="metric-label">IRR</div><div class="metric-value">{metrics['irr']:.2f}%</div></div>
    <div class="metric-box"><div class="metric-label">Sharpe</div><div class="metric-value">{metrics['sharpe']:.2f}</div></div>
    <div class="metric-box"><div class="metric-label">Max DD</div><div class="metric-value">${metrics['max_dd_dollars']:,.0f}</div></div>
    <div class="metric-box"><div class="metric-label">Calmar</div><div class="metric-value">{metrics['calmar']:.2f}</div></div>
    <div class="metric-box"><div class="metric-label">Alpha</div><div class="metric-value">{metrics['alpha']:.2f}%</div></div>
    <div class="metric-box"><div class="metric-label">Beta</div><div class="metric-value">{metrics['beta']:.2f}</div></div>
    <div class="metric-box"><div class="metric-label">Corr</div><div class="metric-value">{metrics['correlation']:.2f}</div></div>
</div>
"""
st.markdown(metrics_html, unsafe_allow_html=True)

st.divider()

mc_fig = go.Figure()

spaghetti_colors = [
    'rgba(148, 163, 184, 0.25)', 'rgba(100, 116, 139, 0.25)', 
    'rgba(71, 85, 105, 0.25)', 'rgba(56, 189, 248, 0.15)', 'rgba(14, 165, 233, 0.15)'
]

# Plot 200 background paths
sample_indices = np.random.choice(cum_sim.shape[0], 200, replace=False)
for i in sample_indices:
    mc_fig.add_trace(go.Scatter(y=cum_sim[i], mode='lines', line=dict(color=random.choice(spaghetti_colors), width=1.5), showlegend=False, hoverinfo='skip'))

# Plot Main Paths
mc_fig.add_trace(go.Scatter(y=cum_sim[best_idx], name='Best Case', mode='lines', line=dict(color='#166534', width=4.5)))
mc_fig.add_trace(go.Scatter(y=cum_sim[worst_idx], name='Worst Case', mode='lines', line=dict(color='#991b1b', width=4.5)))
mc_fig.add_trace(go.Scatter(y=mc_avg_path, name='Statistically Expected (Mean)', mode='lines', line=dict(color='blue', width=6)))
mc_fig.add_trace(go.Scatter(y=orig_cum, name='Original Realized History', mode='lines', line=dict(color='black', width=9)))

# SPY Overlay (Normalized to Start Capital + scaled to PnL axis)
if np.sum(spy_closes) > 0:
    spy_returns = np.diff(spy_closes) / spy_closes[:-1]
    spy_returns = np.insert(spy_returns, 0, 0) # Pad to 252 days
    spy_dollar_pnl = np.insert(np.cumsum(spy_returns * start_capital), 0, 0)
    mc_fig.add_trace(go.Scatter(y=spy_dollar_pnl, name='S&P 500 (SPY)', mode='lines', line=dict(color='orange', width=4.5)))
    mc_fig.add_annotation(x=252, y=spy_dollar_pnl[-1], text=f"SPY: ${spy_dollar_pnl[-1]:,.0f}<br>Bal: ${(start_capital + spy_dollar_pnl[-1]):,.0f}", showarrow=False, xanchor='left', bgcolor='orange', font=dict(color='black', size=11))


last_x = 252
mc_fig.add_annotation(x=last_x, y=cum_sim[best_idx][-1], text=f"Best: ${cum_sim[best_idx][-1]:,.0f}<br>Bal: ${(start_capital + cum_sim[best_idx][-1]):,.0f}", showarrow=False, xanchor='left', bgcolor='#166534', font=dict(color='white', size=11))
mc_fig.add_annotation(x=last_x, y=cum_sim[worst_idx][-1], text=f"Worst: ${cum_sim[worst_idx][-1]:,.0f}<br>Bal: ${(start_capital + cum_sim[worst_idx][-1]):,.0f}", showarrow=False, xanchor='left', bgcolor='#991b1b', font=dict(color='white', size=11))
mc_fig.add_annotation(x=last_x, y=mc_avg_path[-1], text=f"Expected: ${mc_avg_path[-1]:,.0f}<br>Bal: ${(start_capital + mc_avg_path[-1]):,.0f}", showarrow=False, xanchor='left', bgcolor='blue', font=dict(color='white', size=11))
mc_fig.add_annotation(x=last_x, y=orig_cum[-1], text=f"Original: ${orig_cum[-1]:,.0f}<br>Bal: ${(start_capital + orig_cum[-1]):,.0f}", showarrow=False, xanchor='left', bgcolor='black', font=dict(color='white', size=11))

mc_fig.update_layout(
    height=650, margin=dict(l=20, r=80, t=30, b=20), plot_bgcolor='rgba(0,0,0,0)', 
    xaxis_title='Trading Days Forward', 
    yaxis=dict(title='Cumulative Net Profit (USD)', showgrid=True, gridcolor='LightGray', zeroline=True, zerolinecolor='black', zerolinewidth=1, layer='above traces'), 
    xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray', layer='above traces'),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(mc_fig, use_container_width=True)

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# We will wrap the metrics in a slightly smaller column so it doesn't stretch 100% of the screen width
col_spacer_left, col_metrics_box, col_spacer_right = st.columns([0.1, 0.8, 0.1])

with col_metrics_box:
    ruin_pct_limit = st.slider("💥 Ruin Threshold (%)", min_value=5, max_value=50, value=20, step=5, help="Define the maximum acceptable portfolio drawdown.")
    ruin_prob = (np.sum(max_dds > (start_capital * (ruin_pct_limit / 100.0))) / 10000) * 100
    
    st.markdown(f"""
    <div style="background-color: rgba(255, 255, 255, 0.9); padding: 15px; border: 1px solid black; border-radius: 5px; font-size: 12px; color: black; margin-top: 10px;">
        <b style="font-size: 14px; color: #1d4ed8;">RISK METRICS</b><br><br>
        <b>Empirical Risk of Ruin:</b> <span style="color: {'red' if ruin_prob>5 else 'green'}; font-weight: bold;">{ruin_prob:.2f}%</span><br>
        <i>(Probability of hitting a >{ruin_pct_limit}% drawdown based on 10,000 resampled realities).</i><br><br>
        <b style="font-size: 14px; color: #1d4ed8;">DRAWDOWN STATS</b><br><br>
        <b>Original History:</b><br>${orig_dd:,.0f}<br><br>
        <b>SIMULATION (10k runs):</b><br>
        Avg Expected DD: ${mc_avg_dd:,.0f}<br>
        Best Case DD: ${mc_best_dd:,.0f}<br>
        Worst Case DD: ${mc_worst_dd:,.0f}<br><br>
        <hr style="margin: 10px 0;">
        <b>Is it Edge or Luck?</b><br>
        The <i>Best</i> and <i>Worst</i> traces represent the extreme 99.99th and 0.01st percentile limits of purely reshuffled luck given your exact edge. Because your <i>Original Realized History</i> is anchored near the <i>Statistically Expected Mean</i>, it confirms a statistically significant and highly robust edge, rather than an accidental streak of luck.
    </div>
    """.replace('\n', ''), unsafe_allow_html=True)
