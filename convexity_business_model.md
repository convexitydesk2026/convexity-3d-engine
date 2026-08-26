# Convexity Desk: Business & Monetization Model

## 1. Brand Identity & Core Philosophy
**"Mechanical Risk Management."**
Convexity Desk is not a noisy chatroom, a stock-picking discord, or a financial advisory service. It is a clinical, objective, and mechanical platform designed for advanced retail traders who want to map risk and identify asymmetric convexity. 

*   **Vibe:** Institutional, clean, mechanical, and data-driven. Zero clutter. 
*   **Liability Shield:** All interactive tools are strictly "calculators" requiring user inputs. All alerts are "data screens" (e.g., 13F filings hitting moving averages). All trade analyses are provided *after the fact* for educational purposes.

---

## 2. Subscription Tiers

### Tier 1: Free (Top of Funnel & Lead Generation)
**Goal:** Drive SEO traffic, capture email addresses, and demonstrate the mechanical superiority of our risk tools.
*   **Monte Carlo PnL Simulator (Interactive Web Tool):** A fully public, interactive Streamlit tool embedded via iframe. Users can stress-test their win/loss ratios.
*   **Curated Squawk Box:** A clean, noise-free feed of major market catalysts and macroeconomic data points.
*   **The Weekend Post-Mortem (Newsletter):** A free weekly email breaking down a trade the GOAT oven caught *last week*, dissecting the mechanics and the Edge Profile (EP) to prove the system works.

### Tier 2: Base / "The Tracker" ($9 / month)
**Goal:** Extremely low barrier to entry. Provides automated, mechanical data screens for traders who want high-signal alerts without the noise of Twitter or Reddit.
*   **GOAT Oven Alerts:** Automated alerts tracking "Smart Money" (13F filings, US Congress trades). Triggers are purely mechanical (e.g., alert fires only when the stock crosses the 200 SMA).
*   **Pre-Flight Matrix & Options Governor:** A daily mechanical checklist and risk-parameter guide that traders must consult before executing flow.
*   **Market Flow Table (End of Day):** Access to the daily summary of institutional options flow.

### Tier 3: Pro / "The Alpha Engine" ($29 / month)
**Goal:** The core recurring revenue driver. Catering to serious options traders who require pre-market edges and interactive 3D topography tools.
*   **Everything in Base.**
*   **Daily EP Alerts (Pre-Market):** Highly curated, pre-market Edge Profile alerts requiring daily monitoring. These pinpoint specific asymmetric setups before the bell rings.
*   **3D Institutional Options Topography Engine:** Full access to the interactive 3D Greek surface generator (Streamlit iframe hidden behind the Ghost paywall). Users can upload their own CSVs to map their exact VRP contracts.
*   **Alpha Risk Calculator & HWM (High Water Mark) Budget:** Advanced interactive tools for professional bankroll management, risk-of-ruin calculation, and drawdown control.

---

## 3. Technology Stack & Delivery
*   **Website & Paywall:** Ghost CMS. Handles all landing pages, blog posts, email newsletters, and Stripe credit card processing natively.
*   **Interactive Tools:** Streamlit. Apps (Monte Carlo, 3D Engine) are built in Python and hosted on Streamlit Community Cloud.
*   **The Bridge:** Streamlit apps are embedded into Ghost pages using `<iframe>`. Public pages house the free tools; "Members Only" pages house the Pro tools.

## 4. Why This Works (The Competitive Edge)
1.  **Noise Reduction:** Competitors like FlowAlgo provide a firehose of raw data that overwhelms retail traders. Convexity Desk provides *curated, mechanical triggers*.
2.  **Visual Superiority:** Retail brokers (IBKR, ThinkOrSwim) have notoriously clunky UI for risk visualization. Convexity's 3D Topography and Monte Carlo UI feel like a modern, premium SaaS.
3.  **Stress-Free Operations:** No direct broker API integrations = zero liability and zero customer support nightmares regarding broken connections or missed fills.
