import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header

st.set_page_config(page_title="Multi-Account Aggregation | Convexity Desk", layout="wide")

render_global_sidebar()

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

render_page_header("💼 Multi-Account Aggregation", "Consolidated Global Risk & Performance Metrics")

st.markdown("---")

st.info("💡 **Educational Example:** This module demonstrates how institutional software consolidates multiple retail accounts (e.g., 401k, Swing Trading, Options) into a single risk profile.")

# Mock Data for Aggregation
data = {
    "Entity": ["GLOBAL PORTFOLIO", "S&P 500 (SPY)", "NASDAQ 100 (QQQ)"],
    "Balance": ["$972,950", "$1,123,408", "$1,113,809"],
    "IRR": ["15.38%", "20.94%", "19.34%"],
    "PnL": ["$134,613", "$128,945", "$119,346"],
    "Sharpe": ["1.85", "1.01", "0.63"],
    "Max DD": ["-8.44%", "-9.15%", "-15.07%"],
    "DD Days": ["32 d", "110 d", "76 d"],
    "Calmar": ["1.82", "2.29", "1.28"],
    "ROC": ["14.17%", "12.97%", "12.00%"],
    "Alpha": ["5.63%", "-10.63%", "-9.31%"],
    "Beta": ["0.35", "0.45", "0.79"],
    "Corr": ["0.21", "0.41", "0.51"]
}
df_agg = pd.DataFrame(data)

st.dataframe(df_agg, use_container_width=True, hide_index=True)

st.markdown("<div style='text-align: center; color: #64748b; font-size: 12px; margin-bottom: 30px;'>MACRO & OPTIMAL RANGES: Risk-Free Yield (^IRX): 4.15% | IRR: >10% | Sharpe: 1.0 to 2.0+ | Max DD: > -15% | Calmar: > 1.0 | Alpha: > 0% | Corr: 0.30 to 0.60</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

def plot_mini_chart(color):
    fig = go.Figure()
    y_vals = np.cumsum(np.random.normal(0.001, 0.01, 100))
    fig.add_trace(go.Scatter(y=y_vals, mode='lines', line=dict(color='black', width=2)))
    fig.update_layout(
        height=150, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor=color, paper_bgcolor='white', showlegend=False
    )
    return fig

with col1:
    st.markdown("#### Account A (Core 401K)")
    st.caption("Bal: $500,000.00")
    st.plotly_chart(plot_mini_chart("#86efac"), use_container_width=True)
    st.markdown("IRR: 18.73% <br> Sharpe: 1.02 <br> Max DD: -12.42%", unsafe_allow_html=True)

with col2:
    st.markdown("#### Account B (High Beta)")
    st.caption("Bal: $250,000.00")
    st.plotly_chart(plot_mini_chart("#93c5fd"), use_container_width=True)
    st.markdown("IRR: 24.14% <br> Sharpe: 1.20 <br> Max DD: -18.23%", unsafe_allow_html=True)

with col3:
    st.markdown("#### Account C (Speculative)")
    st.caption("Bal: $100,000.00")
    st.plotly_chart(plot_mini_chart("#c084fc"), use_container_width=True)
    st.markdown("IRR: 52.06% <br> Sharpe: 0.85 <br> Max DD: -32.74%", unsafe_allow_html=True)

with col4:
    st.markdown("#### Account D (Options / VRP)")
    st.caption("Bal: $150,000.00")
    st.plotly_chart(plot_mini_chart("#fcd34d"), use_container_width=True)
    st.markdown("IRR: 14.50% <br> Sharpe: 1.95 <br> Max DD: -4.10%", unsafe_allow_html=True)

st.markdown("---")

with st.expander("🏦 View GAAP Balance Sheet & Allocation", expanded=True):
    st.markdown("#### GAAP Balance Sheet (USD)")
    
    silos = ['Silo B', 'Silo A', 'Silo C']
    cash = [20000, 85000, 45000]
    iv_yield = [5000, 450000, 290000]
    physical = [5000, 40000, 30000]
    synthetic = [1000, 15000, 2000]
    
    fig_bs = go.Figure()
    fig_bs.add_trace(go.Bar(name='Cash (15.3%)', x=silos, y=cash, marker_color='#86efac'))
    fig_bs.add_trace(go.Bar(name='IV0 (74.3%)', x=silos, y=iv_yield, marker_color='#93c5fd'))
    fig_bs.add_trace(go.Bar(name='Physical US Stocks (7.7%)', x=silos, y=physical, marker_color='#3b82f6'))
    fig_bs.add_trace(go.Bar(name='Synthetic Beta (1.6%)', x=silos, y=synthetic, marker_color='#1d4ed8'))
    fig_bs.add_trace(go.Bar(name='Tail Hedge (0.5%)', x=silos, y=[0, 5000, 1000], marker_color='#0f172a'))
    fig_bs.add_trace(go.Scatter(name='Margin Debt ($0) (0.0%)', x=silos, y=[0, 0, 0], mode='markers', marker=dict(color='#ef4444', symbol='diamond', size=10)))
    
    fig_bs.update_layout(
        barmode='stack',
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
        yaxis=dict(gridcolor='#e2e8f0'),
        height=350
    )
    
    totals = [31000, 595000, 368000]
    for i, total in enumerate(totals):
        fig_bs.add_annotation(x=silos[i], y=total, text=f"${total/1000:.0f}k", showarrow=False, yshift=10, font=dict(color="#475569", size=10))

    st.plotly_chart(fig_bs, use_container_width=True)
    
    st.markdown("---")
    
    col_pie1, col_pie2 = st.columns(2)
    
    with col_pie1:
        st.markdown("#### Gross Asset Allocation")
        fig_gaa = go.Figure(data=[go.Pie(
            labels=['IV0', 'Cash', 'Physical US Stocks', 'Synthetic Beta', 'Tail Hedge'],
            values=[74.3, 15.3, 7.7, 1.6, 0.5],
            hole=.4,
            marker=dict(colors=['#93c5fd', '#86efac', '#3b82f6', '#1d4ed8', '#0f172a']),
            textinfo='label+percent',
            textposition='inside',
            insidetextorientation='radial'
        )])
        fig_gaa.update_layout(margin=dict(l=20, r=20, t=20, b=20), showlegend=False, height=300)
        st.plotly_chart(fig_gaa, use_container_width=True)
        st.markdown("<div style='text-align: center; color: #475569; font-size: 12px;'><span style='color:#93c5fd'>■</span> IV0 (74.3%) &nbsp; <span style='color:#86efac'>■</span> Cash (15.3%) &nbsp; <span style='color:#3b82f6'>■</span> Physical US Stocks (7.7%) &nbsp; <span style='color:#1d4ed8'>■</span> Synthetic Beta (1.6%) &nbsp; <span style='color:#0f172a'>■</span> Tail Hedge (0.5%)</div>", unsafe_allow_html=True)

    with col_pie2:
        st.markdown("#### Sector Concentration Risk")
        fig_sec = go.Figure(data=[go.Pie(
            labels=['Tech & Innovation', 'Macro', 'Energy', 'Financials'],
            values=[45.8, 30.2, 14.5, 9.5],
            hole=.4,
            marker=dict(colors=['#0284c7', '#7dd3fc', '#ef4444', '#fbcfe8']),
            textinfo='percent',
            textposition='inside'
        )])
        fig_sec.update_layout(margin=dict(l=20, r=20, t=20, b=20), showlegend=False, height=300)
        st.plotly_chart(fig_sec, use_container_width=True)
        st.markdown("<div style='text-align: center; color: #475569; font-size: 12px;'><span style='color:#0284c7'>■</span> Tech & Innovation (45.8%) &nbsp; <span style='color:#7dd3fc'>■</span> Macro (30.2%) &nbsp; <span style='color:#ef4444'>■</span> Energy (14.5%) &nbsp; <span style='color:#fbcfe8'>■</span> Financials (9.5%)</div>", unsafe_allow_html=True)

render_page_footer("The Multi-Account Aggregation panel mathematically blends multiple distinct accounts into a singular risk profile. It allows traders to monitor their global beta and true portfolio correlation to the S&P 500 across disparate strategies.")
