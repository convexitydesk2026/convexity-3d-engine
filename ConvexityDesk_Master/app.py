import streamlit as st

st.set_page_config(page_title="Convexity Desk | Interactive Tools", layout="wide")

# GLOBAL MOBILE BLOCKER
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
        <p style="font-size: 16px; line-height: 1.5;">The Convexity Desk interactive tools are optimized exclusively for desktop monitors.</p>
        <p style="font-size: 16px; line-height: 1.5; color: #a1a1aa;">Please visit <b>convexitydesk.com</b> on your computer to access the platform.</p>
    </div>
""", unsafe_allow_html=True)

st.title("Convexity Desk: Mechanical Risk Management")
st.warning("⚠️ Website under development. Do not rely on the results. Come back in one week. If you still see this header it means we are NOT yet ready for public use.")
st.markdown("### Institutional Quantitative Research Tools")

st.info("👈 **Please select a tool from the sidebar menu to begin.**")

st.markdown("""
Welcome to the Convexity Desk interactive suite. This platform provides strictly mechanical, objective risk analysis calculators. 

**Available Modules:**
*   **Monte Carlo PnL Simulator:** Stress-test win/loss ratios across 10,000 reshuffled realities to determine Risk of Ruin and empirical edge.
*   **3D Options Topography Engine:** Visualize Gamma cliffs, Theta glide paths, and Volatility shocks on your live credit spreads.

*(More modules including the Daily PnL Trajectory and Physical Equity Risk Ledger are currently in development).*
""")
