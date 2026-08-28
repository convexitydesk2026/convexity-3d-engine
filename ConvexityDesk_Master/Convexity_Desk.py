import streamlit as st
from public_core_math import render_page_footer, render_global_sidebar, render_page_header

st.set_page_config(page_title="Convexity Desk | Quant Engine", layout="wide", initial_sidebar_state="expanded")

render_global_sidebar()

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
        /* Compact Card & Button Styling */
        div[data-testid="stPageLink"] a {
            background-color: #2563eb !important; /* High contrast blue */
            color: white !important;
            padding: 8px 14px !important;
            border-radius: 6px !important;
            text-decoration: none !important;
            font-weight: bold !important;
            font-size: 0.9rem !important;
            transition: all 0.2s ease-in-out;
            display: inline-flex;
            justify-content: center;
            width: 220px !important; /* Equal size for all buttons */
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        div[data-testid="stPageLink"] a p, div[data-testid="stPageLink"] a span {
            color: white !important;
            font-weight: bold !important;
        }
        div[data-testid="stPageLink"] a:hover {
            background-color: #1d4ed8 !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        /* Reduce padding in container to make cards tighter */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 0.8rem 1rem !important;
        }
        /* Reduce bottom margin of h4 inside cards */
        div[data-testid="stVerticalBlockBorderWrapper"] h4 {
            margin-bottom: 0.2rem !important;
            padding-bottom: 0 !important;
        }
        .card-desc {
            margin-bottom: 0.6rem !important;
            font-size: 0.85rem !important;
            line-height: 1.3 !important;
            color: #a1a1aa;
        }

        /* Premium Header Styling */
    <div class="mobile-blocker">
        <h1 style="font-size: 24px; color: #ff4b4b; margin-bottom: 20px;">Desktop Only</h1>
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

render_page_header("Convexity Desk", "Institutional Quantitative Research and Risk Management.")

st.markdown("### 🎛️ Active Modules")

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


col3, col4 = st.columns(2)

with col3:
    with st.container(border=True):
        st.markdown("#### 🌊 Market Flow Matrix")
        st.markdown("<div class='card-desc'>Access real-time global institutional rotation data. Instantly identify Momentum Breakouts, Bottom Fishing, and covert Institutional Distribution.</div>", unsafe_allow_html=True)
        st.page_link("pages/5_🌊_Market_Flow_Matrix.py", label="Launch Matrix", icon="🚀")

with col4:
    with st.container(border=True):
        st.markdown("#### 🛩️ Options Pre-Flight Matrix")
        st.markdown("<div class='card-desc'>Strict mechanical checklist to guarantee pristine trade execution. Mitigate emotional bias by running trades through the pre-flight quantitative filter.</div>", unsafe_allow_html=True)
        st.page_link("pages/6_🛩️_Options_Pre_Flight_Matrix.py", label="Launch Checklist", icon="🚀")


col5, col6 = st.columns(2)

with col5:
    with st.container(border=True):
        st.markdown("#### 📈 GOAT Model Portfolio Trajectory")
        st.markdown("<div class='card-desc'>Track the hypothetical historical performance of the 🔥 GOAT Alpha Engine signals against major benchmarks to verify our quantitative edge.</div>", unsafe_allow_html=True)
        st.page_link("pages/3_📈_Daily_PnL_Trajectory.py", label="Launch Trajectory", icon="🚀")

with col6:
    with st.container(border=True):
        st.markdown("#### 📊 Educational Risk Ledger Sandbox")
        st.markdown("<div class='card-desc'>An ephemeral sandbox ledger. Manually edit the dummy data grid to see how position sizing affects the Monte Carlo and risk models.</div>", unsafe_allow_html=True)
        st.page_link("pages/4_📊_Physical_Equity_Risk_Ledger.py", label="Launch Ledger", icon="🚀")


col7, col8 = st.columns(2)

with col7:
    with st.container(border=True):
        st.markdown("#### 🔥 GOAT Alpha Engine")
        st.markdown("<div class='card-desc'>Premium signal generation. Track Qullamaggie Episodic Pivots, 13F institutional accumulation bases, and live Squawk Box macro alerts.</div>", unsafe_allow_html=True)
        st.page_link("pages/7_🔥_GOAT_Alpha_Engine.py", label="Launch Alpha Engine", icon="🚀")

with col8:
    with st.container(border=True):
        st.markdown("#### 💼 Multi-Account Aggregation")
        st.markdown("<div class='card-desc'>Consolidate disparate accounts (401k, Swing, Options) into a singular risk profile. Monitor global beta and true portfolio correlation.</div>", unsafe_allow_html=True)
        st.page_link("pages/8_💼_Multi_Account_Aggregation.py", label="Launch Aggregation", icon="🚀")

st.divider()


# Add a sidebar link back to the main site
with st.sidebar:
    st.divider()
    st.markdown("### 🌐 Main Site")
    st.markdown('<a href="https://convexitydesk.com" target="_blank" style="text-decoration:none;"><button style="width:100%; padding:8px; border-radius:8px; background-color:#1e293b; color:white; border:1px solid #334155; cursor:pointer;">Return to convexitydesk.com</button></a>', unsafe_allow_html=True)

render_page_footer("The Convexity Desk serves as your master control panel. From here, you can launch various quantitative risk management and journaling modules designed to evaluate portfolio attribution strictly from a mathematical, risk-adjusted framework.")
