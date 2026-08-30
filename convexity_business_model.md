# Convexity Desk: Business & Monetization Model

## 1. Brand Identity & Core Philosophy
**"Mechanical Risk Management."**
Convexity Desk is not a noisy chatroom, a stock-picking discord, or a financial advisory service. It is a clinical, objective, and mechanical platform designed for advanced retail traders who want to map risk and identify asymmetric convexity. 

*   **Vibe:** Institutional, clean, mechanical, and data-driven. Zero clutter. 
*   **The "Air-Gapped Toolkit" Model:** We have explicitly dropped all broker synchronization and liability. Convexity acts as an anonymous calculator in the cloud. User portfolios and risk parameters are stored in a database tied exclusively to randomized tokens (e.g., `user_8F2a9B`), requiring manual or CSV data entry.
*   **Absolute Zero Liability:** Because the database contains zero Personally Identifiable Information (no names, emails, or broker API keys), we achieve zero legal liability and bypass GDPR/CCPA data privacy risks entirely. The platform provides seamless cross-device syncing for users while remaining legally bulletproof for the business.

---

## 2. Subscription Tiers

**Beta Phase Note:** Currently, Convexity Desk is in an Open Beta. All modules are accessible via the Convexity dashboard. Once Beta concludes, authentication and payments will be handled exclusively through the Ghost platform, placing specific premium modules behind a paywall.

### Tier 1: Free (The Educator & Top of Funnel)
**Goal:** Drive SEO traffic, capture email addresses, and demonstrate the mechanical superiority of our risk tools.
*   **Educational Risk Ledger Sandbox:** View and interact with a hypothetical portfolio grid.
*   **Monte Carlo PnL Simulator:** A fully public, interactive tool allowing users to stress-test the Sandbox dummy portfolio to determine Risk of Ruin.
*   **Curated Squawk Box:** A clean, noise-free feed of major market catalysts and macroeconomic data points.
*   **The Weekend Post-Mortem (Newsletter):** A free weekly email breaking down a trade the GOAT oven caught *last week*, dissecting the mechanics to prove the system works.

### Tier 2: The Risk Manager (~$39 - $49 / month)
**Goal:** Provides automated, mechanical data screens and institutional risk modeling for independent traders who have their own setups but need professional bankroll management.
*   **Live Portfolio Data Toggle:** Enables saving and tracking custom ledgers.
*   **Market Flow Matrix:** Access real-time global institutional rotation data.
*   **Options Pre-Flight Matrix:** A daily mechanical checklist and risk-parameter guide.
*   **3D Institutional Options Topography Engine:** Full access to the interactive 3D Greek surface generator.
*   **Alpha Risk Calculator & HWM Budget:** The "Crown Jewel" interactive global sidebar for professional bankroll management and tiered drawdown governance.
*   **Multi-Account Aggregation:** Visual dashboard mathematically blending disparate accounts into a singular institutional risk profile.

### Tier 3: The Alpha Engine (~$79 - $99 / month)
**Goal:** The core recurring revenue driver. Catering to serious traders who require pre-market edges and curated intelligence.
*   **Everything in Tier 2.**
*   **🔥 GOAT Alpha Engine (Pre-Market Pitch Dossier):** Premium signal generation tracking Qullamaggie Episodic Pivots, 13F institutional accumulation bases, and TC2000 Fat Pitch screens. This is a highly curated daily watchlist that can pay for the subscription with a single successful execution.

---

## 3. Technology Stack & Operational Costs

To ensure uptime, performance, and professional presentation during both the Beta and Post-Beta phases, the infrastructure is split between Content (Ghost) and Compute (Render).

*   **Website & Paywall:** Ghost CMS. Handles all landing pages, blog posts, email newsletters, and Stripe credit card processing natively.
*   **Interactive Tools:** Streamlit. The python engine is hosted on **Render.com**.
*   **The Bridge (Authentication & Storage):** Streamlit apps are embedded into Ghost pages using `<iframe>`. When a paying user logs into Ghost, Ghost generates an anonymous JWT token and passes it to the iframe. Streamlit reads this token and queries a lightweight PostgreSQL database on Render to load the user's persistent "Live" state. If no valid token is present, Streamlit blocks access, securing the paywall.

### Estimated Monthly Burn (Post-Beta)
1.  **Ghost(Pro) Creator Plan:** ~$25/month
2.  **Render.com Web Service (Compute):** ~$7 to $21/month.
3.  **Data Feeds:** $0 - $30 (Starting with `yfinance`, upgrading to commercial APIs as revenue scales).
4.  **Database / Storage:** ~$7/month (Render PostgreSQL).
5.  **LLM API (Optional for Paid Tiers):** ~$0.50 per active user (GPT-4o-mini or Claude 3.5 Haiku) for natural language CSV parsing or ledger chatting.

**Total Fixed Monthly Burn:** **~$32 to $50 / month.**

---

## 4. Competitive Matrix (Air-Gapped SaaS vs The Industry)

| Competitor | Their Flaw | Convexity's Edge |
| :--- | :--- | :--- |
| **OptionStrat** | Excellent UI, but entirely focused on single-trade visualization. Offers zero macro context, no portfolio-level risk aggregation, and lacks mechanical position sizing rules. | Provides the same modern 3D UI, but ties it directly into a **global portfolio context** (Multi-Account Aggregation, Monte Carlo stress-testing, and the Alpha Risk Budget). |
| **ThinkOrSwim / IBKR** | Legacy, clunky desktop software from the 1990s. Overwhelming for modeling quick hypotheticals. You must log in to an actual brokerage account to use their tools. | A sleek, instant web app. Users don't need to log in to a broker. They can pull up the 3D Topography engine in 2 seconds to visualize a trade. |
| **TradingView** | Unmatched charting, but extremely weak options topography and virtually non-existent portfolio-level Monte Carlo tracking. | Bridges the quantitative gap. Convexity acts as the ultimate companion tool to a TradingView user. |
| **TraderSync / TradeZella** | Requires direct API connections to brokers. Highly maintenance intensive (brokers constantly break APIs). Massive data privacy and GDPR liabilities. | **Air-gapped and zero liability.** We demand manual/CSV entry, completely eliminating API engineering bloat and technical support tickets. |

---

## 5. Exit Strategy & Valuation Projections

**The "Anti-Enslavement" Strategy:** As a solo-preneur, the goal is not to run this forever, but to build a highly profitable Micro-SaaS and sell the Monthly Recurring Revenue (MRR) and user base to a larger prop firm or competitor (like TradeZella).

### Marketing & Acquisition (Without X.com)
*   **Primary Channel:** YouTube & SEO. High-intent, bottom-of-the-funnel tutorials demonstrating Convexity's math solving specific trading pain points.
*   **Secondary Channel:** Affiliate Marketing. Offering trading influencers a 20-30% recurring cut to drive traffic, turning marketing into a strictly variable cost (zero upfront spend).
*   **Paid Ads:** Testing Google Search intent with a starting budget of $500 - $1,000/month.

### Conservative Financial Projections (Milestone 1: 100 Users)
*   **Users:** 100
*   **Blended ARPU (Average Rev Per User):** $60/month
*   **Gross MRR:** $6,000/month ($72,000 ARR)
*   **Total Expenses:** ~$1,030/month (Fixed tech, Stripe fees, LLM API, Affiliate payouts)
*   **Net Cash Flow:** **~$4,970/month** (82% Net Margin)

### 2-Year Horizon Buyout Target
*   **Target Users:** 300
*   **Target ARR:** $216,000
*   **Micro-SaaS Valuation Multiple:** 3x to 5x ARR
*   **Estimated Exit Value:** **~$650,000 to $1,000,000+** 

*The ultimate moat is not the Python code—it is the uniquely designed workflow linking the 3D Topography to the Tiered Drawdown Governor, and the human curation behind the GOAT Alpha Engine that AI cannot easily replicate.*
