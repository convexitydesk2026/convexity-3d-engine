import numpy as np
import pandas as pd
import yfinance as yf
from datetime import timedelta, date
import logging
import streamlit as st
import io
from pathlib import Path

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def render_page_footer(purpose_text=""):
    st.divider()
    if purpose_text:
        st.markdown(f"**Module Purpose:** *{purpose_text}*")
        st.markdown("<br>", unsafe_allow_html=True)
        
    st.warning("⚠️ **Beta Development Phase:** This platform is currently under active development. While you are welcome to explore the sandbox and interact with the modules, please note that results and simulations are not yet reliable. If you still see this header next week, it means we are continuing to polish the engine. In the meantime, feel free to tinker and use the feedback box below to report bugs!")
    with st.expander("📬 Beta Feedback / Bug Report", expanded=False):
        feedback = st.text_area("Tell us what's broken or what you'd like to see:", placeholder="E.g. The trajectory chart looks static...")
        if st.button("Submit Feedback"):
            if feedback:
                st.success("Thanks! Your feedback has been recorded.")
            else:
                st.error("Please enter some feedback before submitting.")

def render_global_sidebar():
    """Renders the global Alpha Risk Calculator & HWM Budget on the sidebar for all pages."""
    with st.sidebar:
        st.markdown("### 🧮 Alpha Risk Calculator & HWM Budget")
        st.caption("[Read the mathematical methodology here](https://convexitydesk.com/the-math-behind-the-alpha-risk-calculator/)")
        
        c1, c2 = st.columns(2)
        with c1:
            hwm = st.number_input("Peak HWM ($)", value=100000, step=1000, min_value=1)
        with c2:
            nav = st.number_input("Current NAV ($)", value=100000, step=1000)
            
        dd_pct = (nav - hwm) / hwm
        if dd_pct > 0:
            dd_pct = 0.0 
            
        if dd_pct >= -0.05:
            tier_name = "Tier 1 (Peak)"
            tier_color = "#16a34a" 
            multiplier = 1.0
        elif dd_pct >= -0.10:
            tier_name = "Tier 2 (Defensive)"
            tier_color = "#d97706" 
            multiplier = 0.5
        elif dd_pct >= -0.15:
            tier_name = "Tier 3 (Preservation)"
            tier_color = "#ea580c" 
            multiplier = 0.25
        else:
            tier_name = "Tier 4 (Hard Stop)"
            tier_color = "#dc2626" 
            multiplier = 0.0
            
        base_capacity = 20000 
        remaining_capacity = base_capacity * multiplier

        st.markdown(
            f"<div style='background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px;'>"
            f"<p style='font-size: 11px; font-weight: bold; color: #64748b; margin-bottom: 0px;'>TIERED DRAWDOWN GOVERNOR</p>"
            f"<h2 style='color: {tier_color}; margin-top: 0px; margin-bottom: 5px;'>{tier_name} ({multiplier}x)</h2>"
            f"<p style='font-size: 12px; color: #475569; margin-bottom: 15px;'>HWM: ${hwm:,.0f} | Current Drawdown: {dd_pct*100:.2f}%</p>"
            f"<div style='display: flex; justify-content: space-between;'>"
            f"<div>"
            f"<p style='font-size: 10px; font-weight: bold; color: #64748b; margin-bottom: 0px;'>BASE CAPACITY</p>"
            f"<p style='font-size: 16px; font-weight: bold; color: #3b82f6; margin-top: 0px;'>${base_capacity:,.0f}</p>"
            f"</div>"
            f"<div style='text-align: right;'>"
            f"<p style='font-size: 10px; font-weight: bold; color: #64748b; margin-bottom: 0px;'>REMAINING CAPACITY</p>"
            f"<p style='font-size: 16px; font-weight: bold; color: {tier_color}; margin-top: 0px;'>${remaining_capacity:,.0f}</p>"
            f"</div>"
            f"</div>"
            f"</div>", 
            unsafe_allow_html=True
        )
        
        with st.expander("Position Sizing Engine", expanded=False):
            st.selectbox("Target Silo", ["Silo A (Core)", "Silo B (High Beta)", "Silo C (Mega-Cap)", "Silo D (Speculative)"])
            st.markdown(f"<p style='font-size: 12px; color: #64748b;'>Silo NAV: <b>${nav/4:,.0f}</b> (Assumed equal split)<br>Uninvested Cash: <b>${(nav/4)*0.2:,.0f}</b></p>", unsafe_allow_html=True)
            
            st.checkbox("Flag as IPO / Unproven Asset")
            
            st.radio("Entry Type", ["Initial Entry", "Scale-In (Pyramid)"], horizontal=True, label_visibility="collapsed")
            
            st.selectbox("Trade Horizon (ATR Sizing)", ["Short-Term (Daily)", "Medium-Term (Weekly)", "Long-Term (Monthly)"])
            st.text_input("Ticker Symbol")
            
            col1, col2 = st.columns(2)
            with col1:
                base_risk = st.number_input("Base Risk %", value=0.200, step=0.01)
            with col2:
                st.selectbox("Direction", ["Long", "Short"])
                
            st.selectbox("Asset Currency", ["USD"])
            entry = st.number_input("Entry Price (USD)", value=100.00, step=1.0)
            sl = st.number_input("Stop Loss Limit (USD)", value=95.00, step=1.0)
            
            if st.button("Calculate Optimal Size", use_container_width=True):
                risk_amt = nav * (base_risk / 100) * multiplier
                risk_per_share = abs(entry - sl)
                if risk_per_share > 0 and risk_amt > 0:
                    shares = int(risk_amt / risk_per_share)
                    capital_at_risk = shares * entry
                    st.info(f"Optimal Size: **{shares} Shares**\n\nTotal Capital: ${capital_at_risk:,.0f}\n\n*Risk Multiplier applied: {multiplier}x*")
                else:
                    if multiplier == 0.0:
                        st.error("HARD STOP: Tier 4 active. Trading halted.")
                    else:
                        st.error("Invalid Entry or Stop Loss")

def init_global_state():
    """Initializes the Master Ledger in st.session_state if it doesn't exist."""
    if 'master_ledger' not in st.session_state:
        # Load Dummy Data from CSV to allow admin to curate the sandbox
        csv_path = Path(__file__).parent / "dummy_portfolio.csv"
        try:
            df = pd.read_csv(csv_path, parse_dates=['Entry Date', 'Exit Date', 'Expiry'])
            # Ensure proper types
            for col in ['Entry Date', 'Exit Date', 'Expiry']:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            st.session_state.master_ledger = df
        except Exception as e:
            st.error(f"Error loading dummy_portfolio.csv: {e}")
            st.session_state.master_ledger = pd.DataFrame()

def verify_license_key():
    """
    Simulates checking a remote licensing server (e.g., Stripe/Auth).
    Returns True if valid. During Beta, always returns True.
    """
    return True

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

def get_spy_data(end_date, num_days=252, start_date=None):
    if start_date is None:
        start_date = end_date - timedelta(days=365 + 30)
    try:
        spy = yf.Ticker("SPY").history(start=start_date.strftime('%Y-%m-%d'), end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'))
        if spy.empty:
            return np.zeros(num_days)
        
        spy_closes = spy['Close'].values
        # If the fetched data is longer than the PnL array, truncate to the most recent `num_days`
        if len(spy_closes) > num_days:
            spy_closes = spy_closes[-num_days:]
        # If it's shorter, pad it with zeros at the beginning
        elif len(spy_closes) < num_days:
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

@st.cache_data(ttl=3600, show_spinner=False)
def compute_daily_trajectory(df_input):
    import yfinance as yf
    import numpy as np
    
    tickers = df_input['Ticker'].unique().tolist()
    if not tickers:
        return pd.DataFrame()
        
    df_input = df_input.copy()
    df_input['Entry Date'] = pd.to_datetime(df_input['Entry Date'])
    start_date = df_input['Entry Date'].min()
    if pd.isna(start_date):
        start_date = date.today() - timedelta(days=365)
        
    end_date = date.today()
    
    # Download Benchmarks & Tickers (Fetch 75 days early for 50-day SMA)
    fetch_start = start_date - timedelta(days=75)
    all_tickers = tickers + ["SPY", "QQQ", "RSP"]
    try:
        hist_data = yf.download(all_tickers, start=fetch_start, end=end_date + timedelta(days=1), progress=False, auto_adjust=False)['Close']
        if len(all_tickers) == 1:
            hist_data = pd.DataFrame({all_tickers[0]: hist_data})
    except Exception:
        return pd.DataFrame()
        
    # Pre-compute Market Regime SMAs
    hist_data['spy_sma20'] = hist_data['SPY'].rolling(window=20).mean()
    hist_data['spy_sma50'] = hist_data['SPY'].rolling(window=50).mean()
    hist_data['rsp_sma20'] = hist_data['RSP'].rolling(window=20).mean()
    hist_data['rsp_sma50'] = hist_data['RSP'].rolling(window=50).mean()
    
    # Trim to actual start_date
    hist_data = hist_data[hist_data.index.tz_localize(None) >= pd.to_datetime(start_date)].copy()
    
    # Build daily series
    dates = hist_data.index.tz_localize(None)
    res = pd.DataFrame({'date': dates})
    
    # Benchmarks
    for b in ["SPY", "QQQ", "RSP"]:
        if b in hist_data.columns:
            res[b.lower()] = np.array(hist_data[b]).flatten()
            res[b.lower()+'_cum'] = (res[b.lower()] / res[b.lower()].iloc[0]) - 1 if not res.empty and res[b.lower()].iloc[0] > 0 else 0
        else:
            res[b.lower()] = 0
            res[b.lower()+'_cum'] = 0
            
    # Compute Daily PnL & Macro Regime
    silo_a_pnl = np.zeros(len(dates))
    silo_b_pnl = np.zeros(len(dates))
    silo_c_pnl = np.zeros(len(dates))
    silo_d_pnl = np.zeros(len(dates))
    daily_alpha = np.zeros(len(dates))
    
    def get_trend_score(price, sma20, sma50):
        if pd.isna(sma50) or pd.isna(sma20): return 0
        score = 0
        if price > sma50: score += 1
        if price > sma20: score += 1
        if sma20 > sma50: score += 1
        return score
    
    for i, d in enumerate(dates):
        # 1. Compute Macro Regime
        spy = hist_data['SPY'].iloc[i] if not pd.isna(hist_data['SPY'].iloc[i]) else 0
        rsp = hist_data['RSP'].iloc[i] if not pd.isna(hist_data['RSP'].iloc[i]) else 0
        
        spy_score = get_trend_score(spy, hist_data['spy_sma20'].iloc[i], hist_data['spy_sma50'].iloc[i])
        rsp_score = get_trend_score(rsp, hist_data['rsp_sma20'].iloc[i], hist_data['rsp_sma50'].iloc[i])
        
        if spy_score == 3 and rsp_score == 3: alpha = 5
        elif spy_score >= 2 and rsp_score >= 2: alpha = 3 if (spy_score == 2 and rsp_score == 2) else 4
        elif spy_score >= 2 and rsp_score < 2: alpha = 2
        elif spy_score < 2 and rsp_score >= 2: alpha = 1
        else: alpha = 0
        
        daily_alpha[i] = alpha
        
        # 2. Compute Portfolio PnL
        a_val, b_val, c_val, d_val = 0.0, 0.0, 0.0, 0.0
        
        for _, row in df_input.iterrows():
            entry_dt = row['Entry Date']
            exit_dt = pd.to_datetime(row['Exit Date']) if pd.notna(row['Exit Date']) and row['Exit Date'] != '' else pd.Timestamp('2099-01-01')
            if d < entry_dt:
                continue # Trade hasn't started yet
                
            ticker = row['Ticker']
            shares = float(row['Shares'])
            entry_price = float(row['Entry Price'])
            if entry_dt <= d <= exit_dt:
                # Trade is Open: Calculate Unrealized PnL based on Spot Price
                spot = entry_price
                if ticker in hist_data.columns and not pd.isna(hist_data[ticker].iloc[i]):
                    spot = float(hist_data[ticker].iloc[i])
                    
                # Fix Day-1 Anomaly: Anchor entry_price to the actual spot price on the first active trading day
                if 'Real_Entry_Price' not in df_input.columns:
                    df_input['Real_Entry_Price'] = np.nan
                    
                if d >= entry_dt and pd.isna(df_input.at[_, 'Real_Entry_Price']) and ticker in hist_data.columns and not pd.isna(hist_data[ticker].iloc[i]):
                    df_input.at[_, 'Real_Entry_Price'] = spot
                    
                actual_entry = df_input.at[_, 'Real_Entry_Price'] if pd.notna(df_input.at[_, 'Real_Entry_Price']) else entry_price
                
                pnl = shares * (spot - actual_entry)
            else:
                # Trade is Closed: Calculate Realized PnL based on Exit Price
                actual_entry = df_input.at[_, 'Real_Entry_Price'] if 'Real_Entry_Price' in df_input.columns and pd.notna(df_input.at[_, 'Real_Entry_Price']) else entry_price
                if pd.notna(row['Exit Price']) and row['Exit Price'] != '':
                    exit_price = float(row['Exit Price'])
                else:
                    exit_price = actual_entry # Fallback to 0 PnL if no exit price provided
                pnl = shares * (exit_price - actual_entry)
                
            if row['Silo'] == 'A': a_val += pnl
            elif row['Silo'] == 'B': b_val += pnl
            elif row['Silo'] == 'C': c_val += pnl
            elif row['Silo'] == 'D': d_val += pnl
                
        silo_a_pnl[i] = a_val
        silo_b_pnl[i] = b_val
        silo_c_pnl[i] = c_val
        silo_d_pnl[i] = d_val
        
    # We want daily DIFFERENCE for the bar charts
    res['silo_a_pnl'] = np.diff(silo_a_pnl, prepend=0)
    res['silo_b_pnl'] = np.diff(silo_b_pnl, prepend=0)
    res['silo_c_pnl'] = np.diff(silo_c_pnl, prepend=0)
    res['silo_d_pnl'] = np.diff(silo_d_pnl, prepend=0)
    
    res['daily_pnl'] = res['silo_a_pnl'] + res['silo_b_pnl'] + res['silo_c_pnl'] + res['silo_d_pnl']
    res['cum_pnl'] = res['daily_pnl'].cumsum()
    
    # Normalize cumulative PnL so it starts at 0 with benchmarks
    if not res.empty:
        res['cum_pnl'] = res['cum_pnl'] - res['cum_pnl'].iloc[0]
    
    res['alpha_gear'] = daily_alpha
    
    spy_returns = res['spy'].pct_change().fillna(0)
    res['opt_dir'] = np.where(res['spy'] > hist_data['spy_sma50'].values, 'Bull', 'Bear')
    
    return res
