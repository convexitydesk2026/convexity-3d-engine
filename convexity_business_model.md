# Convexity Desk: Business & Monetization Model

## 1. Brand Identity & Core Philosophy
**"Mechanical Risk Management."**
Convexity Desk is not a noisy chatroom, a stock-picking discord, or a financial advisory service. It is a clinical, objective, and mechanical platform designed for advanced retail traders who want to map risk and identify asymmetric convexity. 

*   **Vibe:** Institutional, clean, mechanical, and data-driven. Zero clutter. 
*   **The "Air-Gapped Convexity 2.0" Model:** We have explicitly dropped all "personal journaling" and direct data ingestion. There are no API connections to brokers and no uploaded CSV files from users. The platform is entirely *air-gapped*. Users learn and interact strictly via our curated, dummy "Educational Sandbox". 
*   **Absolute Zero Liability:** By ensuring users never upload their real financial data, we achieve zero legal liability, zero data privacy risks (GDPR/CCPA), and zero database maintenance costs. All tools act as educational calculators.

---

## 2. Subscription Tiers

**Beta Phase Note:** Currently, Convexity Desk is in an Open Beta. All modules are accessible via the Convexity dashboard. Once Beta concludes, authentication and payments will be handled exclusively through the Ghost platform, which will place specific premium modules behind a paywall.

### Tier 1: Free (Top of Funnel & Lead Generation)
**Goal:** Drive SEO traffic, capture email addresses, and demonstrate the mechanical superiority of our risk tools.
*   **Educational Risk Ledger Sandbox:** View and interact with a hypothetical portfolio grid.
*   **Monte Carlo PnL Simulator:** A fully public, interactive tool allowing users to stress-test the Sandbox dummy portfolio to determine Risk of Ruin.
*   **Curated Squawk Box:** A clean, noise-free feed of major market catalysts and macroeconomic data points (Alpha Radar).
*   **The Weekend Post-Mortem (Newsletter):** A free weekly email breaking down a trade the GOAT oven caught *last week*, dissecting the mechanics to prove the system works.

### Tier 2: Base / "The Tracker" ($9 / month)
**Goal:** Extremely low barrier to entry. Provides automated, mechanical data screens for traders who want high-signal alerts without the noise of Twitter or Reddit.
*   **Market Flow Matrix:** Access real-time global institutional rotation data.
*   **Options Pre-Flight Matrix:** A daily mechanical checklist and risk-parameter guide that traders must consult before executing flow.
*   **3D Institutional Options Topography Engine:** Full access to the interactive 3D Greek surface generator. Users interact with dummy options data in the Sandbox to visualize structures.

### Tier 3: Pro / "The Alpha Engine" ($29 / month)
**Goal:** The core recurring revenue driver. Catering to serious traders who require pre-market edges and professional risk management.
*   **Everything in Base.**
*   **🔥 GOAT Alpha Engine:** Premium signal generation tracking Qullamaggie Episodic Pivots and 13F institutional accumulation bases.
*   **GOAT Model Portfolio Trajectory:** The simulated, hypothetical historical track record proving the efficacy of the Alpha Engine against benchmarks.
*   **Alpha Risk Calculator & HWM Budget:** The "Crown Jewel" interactive global sidebar for professional bankroll management, tiered drawdown governance, and position sizing.
*   **Multi-Account Aggregation:** Visual dashboard mathematically blending disparate accounts into a singular institutional risk profile.

---

## 3. Technology Stack & Operational Costs

To ensure uptime, performance, and professional presentation during both the Beta and Post-Beta phases, the infrastructure is split between Content (Ghost) and Compute (Render).

*   **Website & Paywall:** Ghost CMS. Handles all landing pages, blog posts, email newsletters, and Stripe credit card processing natively.
*   **Interactive Tools:** Streamlit. The python engine is hosted on **Render.com** (moving away from Streamlit Community Cloud to avoid app sleep states and memory limits).
*   **The Bridge:** Streamlit apps are linked or embedded into Ghost pages using `<iframe>`. 

### Monthly Cost Breakdown (Beta & Post-Beta)
By remaining air-gapped and utilizing modern PaaS, Convexity 2.0 is incredibly lean:
1.  **Ghost(Pro) Creator Plan:** ~$25/month (Provides custom domain, premium themes, Stripe integration, and newsletter capabilities).
2.  **Render.com Web Service (Compute):** ~$7 to $21/month. A standard Starter tier ($7) is usually sufficient for early Beta traffic. If the numpy/pandas dataframes require more memory as traffic scales, upgrading to Standard ($21) is seamless. 
3.  **Data Feeds:** $0 (Leveraging `yfinance` for end-of-day educational data modeling rather than expensive real-time API subscriptions).
4.  **Database / Storage:** $0 (The air-gapped model means we do not host a PostgreSQL database for user trades).

**Total Estimated Monthly Burn:** **~$32 to $46 / month.**

---

## 4. Competitive Matrix (Air-Gapped 2.0 vs The Industry)

The pivot to "Air-Gapped Convexity 2.0" perfectly positions the platform in a unique, uncrowded niche. Here is how we defeat the competition:

| Competitor | Their Flaw | Convexity 2.0's Edge |
| :--- | :--- | :--- |
| **OptionStrat** | Excellent UI, but entirely focused on single-trade visualization. Offers zero macro context, no portfolio-level risk aggregation, and lacks mechanical position sizing rules. | Provides the same modern 3D UI, but ties it directly into a **global portfolio context** (Multi-Account Aggregation, Monte Carlo stress-testing, and the Alpha Risk Budget). |
| **ThinkOrSwim / IBKR** | Legacy, clunky desktop software from the 1990s. Overwhelming for modeling quick hypotheticals. You must log in to an actual brokerage account to use their tools. | A sleek, instant web app. Users don't need to log in to a broker. They can pull up the 3D Topography engine in 2 seconds to visualize a trade. |
| **TradingView** | Unmatched charting, but extremely weak options topography and virtually non-existent portfolio-level Monte Carlo tracking. | Bridges the quantitative gap. Convexity acts as the ultimate companion tool to a TradingView user. |
| **TraderSync / Journaling Apps** | Requires direct API connections to brokers. Highly maintenance intensive (brokers constantly break APIs). Massive data privacy and GDPR liabilities. | **Air-gapped and zero liability.** We don't want the user's data. We offer a pristine educational sandbox to learn mechanical risk, saving thousands of hours of backend engineering and support tickets. |
