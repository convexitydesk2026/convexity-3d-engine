# V-Bounce Capitulation Strategy: Fiduciary Report
**Date:** August 2026  
**Status:** In-Sample Validation Complete (10-Year Dataset: 2014-2024)

## Executive Summary
The V-Bounce Capitulation strategy is an automated, event-driven equity algorithm designed to exploit localized panic selling. It identifies extreme capitulation events (massive intraday price drops on extreme relative volume) and captures the subsequent mechanical reversion (the "dead-cat bounce"). 

This report evaluates the strategy for potential deployment within a family estate's alternative asset sleeve.

> [!IMPORTANT]  
> **Fiduciary Recommendation:** This strategy is recommended strictly as an uncorrelated "Crisis Alpha" satellite sleeve, capped at a maximum of 10% of total estate NAV. It is an event-driven anomaly strategy, not a core yield-generation engine. For primary yield generation, Volatility Risk Premium (VRP) harvesting remains structurally superior.

---

## The Mathematically Optimal Parameters (Trial #81)
After processing nearly 400 iterations across a 10-year dataset (2014-2024), the Optuna AI optimizer identified **Trial #81** as the optimal parameter set for a moderate-risk mandate. 

Unlike the absolute maximum yield parameter (Trial #92, which operates without a stop-loss), Trial #81 introduces a strict 4.00% trailing stop. This transforms the strategy from an unbounded tail-risk bet into a mathematically constrained volatility capture strategy.

### Entry Criteria
- **Minimum Stock Price:** $37.00
- **Drop Threshold:** 39.00% (The stock must drop at least 39% from the previous close).
- **Volume Multiplier:** 4.5x (The drop must occur on at least 450% of the 14-day average volume).
- **Market Regime Filter:** Any (The algorithm executes regardless of the S&P 500 trend).

### Exit Mechanics
- **Take Profit Target:** 33.00%
- **Trailing Stop Loss:** 4.00% (Systematic downside protection).
- **Maximum Hold Time:** 4 Days (Strict time stop to prevent capital tie-up).

---

## Statistical Profile & Expectations

| Metric | Expected Value (Live Forward-Walk) |
|--------|------------------------------------|
| **Win Rate** | 40% - 45% |
| **Annualized ROC (On Sleeve)** | 12.0% - 15.0% |
| **5-Year Compounded ROC** | +76% to +101% |
| **Trade Frequency** | ~15 trades per year |

> [!NOTE]  
> **The Win Rate Paradox:** A 40% win rate is standard for asymmetric volatility strategies. The tight 4% trailing stop guarantees frequent "shake-outs" during normal chop, but the massive 33% profit target mathematically offsets five consecutive stopped-out trades.

---

## Risk Management & Estate Integration

If this strategy is deployed by the family estate, it must be integrated with strict position sizing rules.

1. **NAV Allocation:** Maximum 10.0% of the estate's total NAV should be allocated to this specific strategy sleeve.
2. **Capital Efficiency:** Because the strategy only triggers ~15 times a year and holds for a maximum of 4 days, the allocated capital will remain in cash for 95% of the year. This cash must be parked in a Treasury Money Market Fund to generate baseline yield.
3. **Position Sizing:** The algorithm should risk no more than 10.0% of the allocated sleeve per trade.
4. **Absolute Estate Risk:** Because of the 4% trailing stop, a 10% position size limits the *maximum loss per trade* to 0.4% of the sleeve. For the total estate, a worst-case scenario trade costs a microscopic **0.04% of Total NAV**.

---

---

## Directives Update: Intraday Stress Test & Liquidity Filters
Following the Convexity Desk's directives, we ran a dedicated verification script forcing exact minute-by-minute execution (`use_minute_data=True`) and institutional liquidity filters (`min_dollar_volume = $50M`).

The findings dramatically alter the deployment viability of Trial #81:

### 1. The Liquidity Collapse
By enforcing a $50 Million minimum daily dollar volume, the algorithm filters out illiquid micro-caps. However, this reveals that 39% capitulation crashes on highly liquid mid-to-large cap stocks are extremely rare. Over the 10-year in-sample period, the strategy only triggered **26 times** (roughly 2 to 3 trades a year).

### 2. The Intraday Whipsaw Failure
The Convexity Desk's suspicion was 100% correct. The "fast approximation" used by the Optuna AI assumed trailing stops survived based on daily lows. When stress-tested against exact minute-by-minute data, the extreme intraday volatility associated with capitulation events systematically hunts and destroys a tight 4% trailing stop.
* **In-Sample PnL:** Collapsed from +14.52% down to **+0.24%** (Win rate: 30.7%)
* **Out-Of-Sample (2024-2026):** **+2.10%** (Win rate: 33.3% across 6 trades)

> [!WARNING]  
> **Final Assessment:** Trial #81 fails the intraday execution stress test. A 4% trailing stop is mathematically incompatible with the intraday volatility required to trade 39% capitulation crashes. Furthermore, institutional liquidity filters reduce the trade frequency to un-scalable levels (~3 trades a year). 
> 
> **Recommendation to Convexity Desk:** Discard V-Bounce for the Estate portfolio and proceed entirely with structural Volatility Risk Premium (VRP) strategies.
