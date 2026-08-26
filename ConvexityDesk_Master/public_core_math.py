import numpy as np
import pandas as pd
import yfinance as yf
from datetime import timedelta
import logging

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def generate_synthetic_pnl(win_rate, avg_win, avg_loss, num_trades):
    """
    Generates a synthetic array of PnL outcomes based on user parameters,
    adding Gaussian noise (variance) to make the simulation realistic.
    """
    outcomes = []
    # Use 50% of the mean as standard deviation to create realistic trade variance
    win_std = avg_win * 0.5
    loss_std = avg_loss * 0.5
    
    for _ in range(num_trades):
        if np.random.rand() < (win_rate / 100.0):
            trade = np.random.normal(loc=avg_win, scale=win_std)
            outcomes.append(max(1.0, trade)) # Ensure it's technically a win
        else:
            trade = np.random.normal(loc=-avg_loss, scale=loss_std)
            outcomes.append(min(-1.0, trade)) # Ensure it's technically a loss
            
    return np.array(outcomes)

def generate_mc_paths(pnl_array):
    np.random.seed(len(pnl_array))
    # Bootstrapping 10,000 paths
    sim_data = np.random.choice(pnl_array, size=(10000, len(pnl_array)), replace=True)
    c_sim = np.cumsum(sim_data, axis=1)
    z_col = np.zeros((10000, 1))
    c_sim = np.hstack((z_col, c_sim))
    
    pks = np.maximum.accumulate(c_sim, axis=1)
    a_dds = pks - c_sim
    m_dds = np.max(a_dds, axis=1)
    
    m_avg_dd = np.mean(m_dds)
    m_best_dd = np.min(m_dds)
    m_worst_dd = np.max(m_dds)
    m_avg_path = np.mean(c_sim, axis=0)
    
    return c_sim, m_dds, m_avg_dd, m_best_dd, m_worst_dd, m_avg_path

def get_spy_data(end_date, num_days=252):
    # Fetch SPY data. We fetch slightly more days (e.g. 400 calendar days) to guarantee we get 252 trading days.
    start_date = end_date - timedelta(days=365 + 30)
    try:
        spy = yf.download("SPY", start=start_date.strftime('%Y-%m-%d'), end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'), progress=False)
        if spy.empty:
            return np.zeros(num_days)
        
        # Get closing prices, limit to exactly `num_days`
        if isinstance(spy.columns, pd.MultiIndex):
            spy_closes = spy['Close'].squeeze().values[-num_days:]
        else:
            spy_closes = spy['Close'].values[-num_days:]
            
        if len(spy_closes) < num_days:
            # If we somehow didn't get enough data, pad with zeros
            spy_closes = np.pad(spy_closes, (num_days - len(spy_closes), 0), 'constant', constant_values=spy_closes[0] if len(spy_closes)>0 else 0)
            
        return spy_closes
    except Exception:
        return np.zeros(num_days)

def calculate_advanced_metrics(daily_pnl, spy_closes, start_capital, risk_free_rate=0.04):
    """
    Calculates IRR, P&L, Sharpe, Max DD, Calmar, ROC, Alpha, Beta, Correlation
    """
    total_pnl = np.sum(daily_pnl)
    roc = (total_pnl / start_capital) * 100
    
    # Since 252 days is exactly 1 year, IRR is practically identical to ROC.
    irr = roc
    
    # Equity curve and drawdown
    equity = start_capital + np.cumsum(daily_pnl)
    peaks = np.maximum.accumulate(equity)
    drawdowns = (peaks - equity) / peaks
    max_dd_pct = np.max(drawdowns) * 100
    max_dd_dollars = np.max(peaks - equity)
    
    # Calmar Ratio (Annualized Return / Max Drawdown)
    calmar = (roc / max_dd_pct) if max_dd_pct > 0 else 0
    
    # Daily Returns of the strategy
    prev_equity = np.insert(equity[:-1], 0, start_capital)
    strategy_returns = daily_pnl / prev_equity
    
    # Sharpe Ratio
    daily_rf = risk_free_rate / 252.0
    excess_returns = strategy_returns - daily_rf
    if np.std(excess_returns) == 0:
        sharpe = 0
    else:
        sharpe = np.sqrt(252) * np.mean(excess_returns) / np.std(excess_returns)
        
    # SPY metrics
    if np.sum(spy_closes) == 0:
        ann_spy_return = 0
        correlation, beta, alpha = 0, 0, 0
    else:
        spy_returns = np.diff(spy_closes) / spy_closes[:-1]
        spy_returns = np.insert(spy_returns, 0, 0) # Pad to 252 days
        
        if np.std(spy_returns) > 0 and np.std(strategy_returns) > 0:
            correlation = np.corrcoef(strategy_returns, spy_returns)[0, 1]
            beta = correlation * (np.std(strategy_returns) / np.std(spy_returns))
            
            ann_strat_return = roc / 100.0
            ann_spy_return = (spy_closes[-1] - spy_closes[0]) / spy_closes[0]
                
            alpha = ann_strat_return - (risk_free_rate + beta * (ann_spy_return - risk_free_rate))
            alpha = alpha * 100 # Convert to percentage
        else:
            correlation, beta, alpha = 0, 0, 0
            ann_spy_return = 0
        
    return {
        "pnl": total_pnl,
        "roc": roc,
        "irr": irr,
        "sharpe": sharpe,
        "max_dd_dollars": max_dd_dollars,
        "max_dd_pct": max_dd_pct,
        "calmar": calmar,
        "alpha": alpha,
        "beta": beta,
        "correlation": correlation,
        "spy_cumulative_return": ann_spy_return * 100,
        "spy_closes": spy_closes
    }
