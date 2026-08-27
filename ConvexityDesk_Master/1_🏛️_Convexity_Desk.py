import streamlit as st
from public_core_math import render_beta_warning_and_feedback

st.set_page_config(page_title="Convexity Desk | Quant Engine", layout="wide", initial_sidebar_state="expanded")

# GLOBAL MOBILE BLOCKER & CUSTOM CSS
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

        /* Premium Header Styling */
        .hero-banner {
            padding: 3rem 2rem;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            border-radius: 12px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #334155;
        }
        
        .hero-title {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            background: -webkit-linear-gradient(45deg, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .hero-subtitle {
            font-size: 1.2rem;
            color: #94a3b8;
            max-width: 700px;
            margin: 0 auto;
        }
        
        /* Module Card Subtitles */
        .card-desc {
            font-size: 0.95rem;
            color: #64748b;
            margin-bottom: 1.5rem;
            line-height: 1.5;
        }
    </style>
    
    <div class="mobile-blocker">
        <h1 style="font-size: 24px; color: #ff4b4b; margin-bottom: 20px;">Desktop Only</h1>
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
    
    <div class="hero-banner">
        <div class="hero-title">Convexity Desk</div>
        <div class="hero-subtitle">Mechanical Risk Management & Institutional Quantitative Research</div>
    </div>
""", unsafe_allow_html=True)

render_beta_warning_and_feedback()

st.markdown("### 🎛️ Active Modules")
st.markdown("<br>", unsafe_allow_html=True)

# Create a 2x2 grid of premium cards
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("#### 🎲 Monte Carlo Simulator")
        st.markdown("<div class='card-desc'>Stress-test win/loss ratios across 10,000 reshuffled realities to determine Risk of Ruin and empirical statistical edge based on your historical trades.</div>", unsafe_allow_html=True)
        st.page_link("pages/1_🎲_Monte_Carlo_Simulator.py", label="Launch Simulator", icon="🚀")

with col2:
    with st.container(border=True):
        st.markdown("#### 📊 3D Options Topography")
        st.markdown("<div class='card-desc'>Visualize complex Gamma cliffs, Theta glide paths, and Volatility shocks on your live credit spreads using interactive 3D surface plane intersections.</div>", unsafe_allow_html=True)
        st.page_link("pages/2_📊_3D_Options_Topography.py", label="Launch Engine", icon="🚀")

st.markdown("<br>", unsafe_allow_html=True)
col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("#### 🌊 Market Flow Matrix")
        st.markdown("<div class='card-desc'>Access real-time global institutional rotation data. Instantly identify Momentum Breakouts, Bottom Fishing, and covert Institutional Distribution.</div>", unsafe_allow_html=True)
        st.page_link("pages/5_🌊_Market_Flow_Matrix.py", label="Launch Matrix", icon="🚀")

with col4:
    with st.container(border=True):
        st.markdown("#### 🛩️ Pre-Flight Matrix")
        st.markdown("<div class='card-desc'>Strict mechanical checklist to guarantee pristine trade execution. Mitigate emotional bias by running trades through the pre-flight quantitative filter.</div>", unsafe_allow_html=True)
        st.page_link("pages/6_🛩️_Pre_Flight_Matrix.py", label="Launch Checklist", icon="🚀")

st.markdown("<br>", unsafe_allow_html=True)
col5, col6 = st.columns(2)

with col5:
    with st.container(border=True):
        st.markdown("#### 📈 Daily PnL Trajectory")
        st.markdown("<div class='card-desc'>Track the daily evolution of your portfolio's PnL against the S&P 500 benchmark. Identify drawdowns and volatility drag in real-time.</div>", unsafe_allow_html=True)
        st.page_link("pages/3_📈_Daily_PnL_Trajectory.py", label="Launch Trajectory", icon="🚀")

with col6:
    with st.container(border=True):
        st.markdown("#### 📊 Physical Equity Risk Ledger")
        st.markdown("<div class='card-desc'>Comprehensive mechanical ledger for physical equity positions. Automatically calculate risk-adjusted position sizing and stop-loss levels.</div>", unsafe_allow_html=True)
        st.page_link("pages/4_📊_Physical_Equity_Risk_Ledger.py", label="Launch Ledger", icon="🚀")

st.divider()

st.markdown("""
<div style='text-align: center; color: #94a3b8; font-size: 0.85rem;'>
    <i>"Do not guess. Do not hope. Measure, quantify, and execute."</i><br><br>
    © 2026 Convexity Desk. All Rights Reserved.
</div>
""", unsafe_allow_html=True)

# Add a sidebar link back to the main site
with st.sidebar:
    st.divider()
    st.markdown("### 🌐 Main Site")
    st.markdown('<a href="https://convexitydesk.com" target="_blank" style="text-decoration:none;"><button style="width:100%; padding:8px; border-radius:8px; background-color:#1e293b; color:white; border:1px solid #334155; cursor:pointer;">Return to convexitydesk.com</button></a>', unsafe_allow_html=True)
