import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header, init_global_state

st.set_page_config(page_title="Glossary & References | Convexity Desk", layout="wide")

render_global_sidebar()
init_global_state()

render_page_header("📖 Glossary and References", "Key terms, mathematical methodologies, and foundational literature.")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 🏛️ Convexity Desk Terminology")
    
    with st.expander("Tiered Drawdown Governor", expanded=True):
        st.markdown("""
        A mechanical risk-management multiplier designed to prevent catastrophic ruin. It tracks your portfolio's **High-Water Mark (HWM)** and automatically scales down your base risk capacity as your account draws down. 
        * **Tier 1 (0 to -5% DD):** 1.0x Base Risk
        * **Tier 2 (-5% to -10% DD):** 0.5x Base Risk
        * **Tier 3 (-10% to -15% DD):** 0.25x Base Risk
        * **Tier 4 (<-15% DD):** 0.0x (Hard Stop)
        """)
        
    with st.expander("Monte Carlo Simulation"):
        st.markdown("""
        A probabilistic risk model that takes your historical win rate, average win, and average loss, and reshuffles those outcomes across **10,000 hypothetical 1-year trajectories**. It explicitly reveals your **Risk of Ruin** (the probability of blowing up your account) and your expected median drawdown based on your *actual* historical edge.
        """)

    with st.expander("3D Options Topography"):
        st.markdown("""
        Rather than looking at a flat 2D PnL chart at expiration, Topography maps the options Greeks (Gamma, Theta, Vega) across three dimensions: **Underlying Price**, **Days to Expiration (DTE)**, and **Implied Volatility**. It visualizes the "Gamma Cliffs" and "Theta Sinks" that trap novice option sellers before expiration.
        """)

    with st.expander("Qullamaggie Episodic Pivot (EP)"):
        st.markdown("""
        A highly specific breakout setup popularized by Kristjan Kullamägi. It requires a massive fundamental catalyst (e.g., surprise earnings, FDA approval) resulting in a massive gap up (>10%) accompanied by extreme relative volume (>5x). Convexity Desk tracks these in the **GOAT Alpha Engine**.
        """)

    with st.expander("13F Accumulation Base"):
        st.markdown("""
        A long-term structural setup identified by tracking SEC 13F filings of elite proprietary firms (e.g., Duquesne Family Office). When institutional volume accumulates a stock sideways for months, we flag it in the **GOAT Oven** waiting for a breakout.
        """)

with col2:
    st.markdown("### 📚 Foundational Literature")
    st.markdown("The quantitative models powering Convexity Desk are built upon decades of institutional research. Below are public whitepapers and literature that define our mathematical engine.")
    
    with st.container(border=True):
        st.markdown("#### Options & Volatility Risk Premium")
        st.markdown("- 🔗 [**Understanding the Volatility Risk Premium (AQR)**](https://www.aqr.com/-/media/AQR/Documents/White-Papers/Understanding-the-Volatility-Risk-Premium.pdf) - Explains why option sellers are historically compensated for taking on negative convexity.")
        st.markdown("- 🔗 [**CBOE VIX Whitepaper**](https://cdn.cboe.com/resources/vix/vixwhite.pdf) - The mechanical foundation for understanding implied volatility pricing and variance swaps.")
        st.markdown("- 🔗 [**Dynamic Hedging (Nassim Taleb)**](https://archive.org/) - The foundational textbook on managing nonlinear risk and Gamma exposure.")

    with st.container(border=True):
        st.markdown("#### Portfolio Sizing & Risk Management")
        st.markdown("- 🔗 [**The Kelly Criterion in Blackjack Sports Betting, and the Stock Market**](https://www.stat.berkeley.edu/~aldous/157/Papers/Goodall.pdf) - The mathematical proof for optimal bet sizing to maximize geometric growth rate.")
        st.markdown("- 🔗 [**Trend Following (Michael Covel)**](https://www.trendfollowing.com/) - The philosophy behind mechanical stop-losses, ignoring narratives, and strict price-action risk modeling.")

st.markdown("---")
st.markdown("### ❓ Frequently Asked Questions (Q&A)")

q1, q2 = st.columns(2)
with q1:
    with st.expander("Why doesn't Convexity Desk sync directly with my broker API?"):
        st.markdown("Direct broker APIs are highly unstable, prone to breaking during platform updates, and create massive data privacy liabilities. By requiring manual or CSV ledger entry, we ensure **100% data privacy** (Air-Gapped) and zero downtime due to third-party API failures. You own your data.")
    with st.expander("Does Convexity Desk provide automated trading bots?"):
        st.markdown("No. Convexity Desk provides **Signals** (via the GOAT Alpha Engine) and **Risk Math** (via the Drawdown Governor). We are an institutional toolkit, not a black-box trading algorithm. Execution remains entirely in the hands of the discretionary trader.")

with q2:
    with st.expander("How accurate is the Monte Carlo Simulator?"):
        st.markdown("It is mathematically pure, but it relies entirely on the accuracy of your historical inputs (Win Rate, Avg Win, Avg Loss). If you feed it a ledger of undisciplined, random trades, the simulation will show a high Risk of Ruin. It reflects your *actual* mechanical edge, not theoretical potential.")
    with st.expander("What is the difference between the Sandbox and the Live Portfolio?"):
        st.markdown("The **Educational Sandbox** uses pre-loaded dummy data to allow you to safely experiment with position sizing and stress-test the math. The **Live Portfolio** is an empty schema where you can upload your actual historical CSV trade log to map your real-world equity curve.")

render_page_footer("The Glossary ensures all Convexity Desk operators share a unified, institutional vernacular. We do not gamble; we execute math.")
