# Estate Directives Implementation Plan

This plan addresses the three directives requested by the Convexity Desk (Estate AI) to move the V-Bounce strategy from an in-sample concept to a live deployment candidate.

## 1. Intraday Stress-Testing of the Trailing Stop
The Estate AI correctly identified a major risk. The massive 500-trial Optuna backtest running in the background uses **daily bar approximation** (`use_minute_data=False`) for processing speed. This means it assumes a trailing stop is triggered if the daily `low` breaches the level, but it does not account for exact minute-by-minute whipsaws.

**Proposed Action:**
I will create a standalone script (`verify_trial_81.py`) that strictly enforces `use_minute_data=True`. It will run Trial #81 over the in-sample period (2016-2024) and fetch the exact 1-minute bars from the PostgreSQL database for every triggered trade. This will prove definitively whether the 4% trailing stop survives true intraday volatility or gets consistently stopped out 15 minutes after entering.

## 2. Enforce Absolute Liquidity Filters
The current optimizer searches for minimum dollar volumes between $500k and $10M. The Estate AI demands a strict minimum of $50 Million Average Daily Dollar Volume to ensure institutional-grade liquidity and tight spreads.

**Proposed Action:**
I will modify `optimize_v_bounce.py` and the standalone verification script to hardcode `min_dollar_volume = 50000000`. 
#### [MODIFY] optimize_v_bounce.py
```python
# Old: 
min_dollar_volume = trial.suggest_int('min_dollar_volume', 500000, 10000000, step=500000)
# New:
min_dollar_volume = 50000000  # Enforced Estate Directive ($50M)
```

## 3. Proceed with Out-Of-Sample (OOS) Validation
The ultimate test of algorithmic robustness is how it performs on data the AI has never seen before.

**Proposed Action:**
I will configure `verify_trial_81.py` to run across the **Out-Of-Sample dataset (Jan 1, 2024 to Present)**. It will incorporate all Estate directives:
- Trial #81 Parameters
- $50 Million Dollar Volume Filter
- `use_minute_data=True` (Minute-by-minute stress testing)

## Verification Plan
1. Provide the In-Sample Intraday Stress Test results (Win rate / Avg PnL).
2. Provide the Out-Of-Sample (OOS) Forward Walk results (Win rate / Avg PnL) for 2024-2026 to see if the alpha holds up in unseen markets.
