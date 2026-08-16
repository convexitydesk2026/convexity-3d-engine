import pandas as pd
from risk_engine import calculate_hwm_budget

def test_tier_1_peak_performance():
    # Mock Data: HWM is $100,000. Current NAV is $100,000 (0% Drawdown)
    df = pd.DataFrame({'date': [pd.to_datetime('2026-08-01')], 'nav': [100000]})
    hwm, dd_pct, mult, name = calculate_hwm_budget(df, 100000)
    
    assert mult == 1.0
    assert name == "Tier 1 (Peak)"

def test_tier_2_caution_zone():
    # Mock Data: HWM is $100,000. Current NAV is $98,500 (-1.5% Drawdown)
    df = pd.DataFrame({'date': [pd.to_datetime('2026-08-01')], 'nav': [100000]})
    hwm, dd_pct, mult, name = calculate_hwm_budget(df, 98500)
    
    assert mult == 0.5
    assert name == "Tier 2 (Caution)"

def test_tier_4_system_lockout():
    # Mock Data: HWM is $100,000. Current NAV is $95,000 (-5.0% Drawdown)
    df = pd.DataFrame({'date': [pd.to_datetime('2026-08-01')], 'nav': [100000]})
    hwm, dd_pct, mult, name = calculate_hwm_budget(df, 95000)
    
    assert mult == 0.0
    assert name == "Tier 4 (Lockout)"