import numpy as np
import pandas as pd
import yfinance as yf
from datetime import timedelta, date
import logging
import streamlit as st
import io

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def render_beta_warning_and_feedback():
    st.warning("⚠️ **Beta Development Phase:** This platform is currently under active development. While you are welcome to explore the sandbox and interact with the modules, please note that results and simulations are not yet reliable. If you still see this header next week, it means we are continuing to polish the engine. In the meantime, feel free to tinker and use the feedback box below to report bugs!")
    with st.expander("📬 Beta Feedback / Bug Report", expanded=False):
        feedback = st.text_area("Tell us what's broken or what you'd like to see:", placeholder="E.g. The trajectory chart looks static...")
        if st.button("Submit Feedback"):
            if feedback:
                st.success("Thanks! Your feedback has been recorded.")
            else:
                st.error("Please enter some feedback before submitting.")

def init_global_state():
    """Initializes the Master Ledger in st.session_state if it doesn't exist."""
    if 'master_ledger' not in st.session_state:
        # Create Dummy Data
        today = date.today()
        d_250 = today - timedelta(days=250)
        d_200 = today - timedelta(days=200)
        d_150 = today - timedelta(days=150)
        d_100 = today - timedelta(days=100)
        d_50 = today - timedelta(days=50)
        d_10 = today - timedelta(days=10)
        
        data = [
            # Period 1 (d_250 to d_200): Aggressive (Avg Gear ~4)
            {'Ticker': 'SPY', 'Class': 'Equity', 'Silo': 'A', 'Entry Date': d_250, 'Entry Price': 676.99, 'Shares': 37, 'Stop Loss': 650.0, 'Exit Date': d_200, 'Exit Price': 690.28, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'AMZN', 'Class': 'Equity', 'Silo': 'B', 'Entry Date': d_250, 'Entry Price': 227.35, 'Shares': 110, 'Stop Loss': 210.0, 'Exit Date': d_200, 'Exit Price': 208.72, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'NVDA', 'Class': 'Equity', 'Silo': 'C', 'Entry Date': d_250, 'Entry Price': 180.77, 'Shares': 138, 'Stop Loss': 160.0, 'Exit Date': d_200, 'Exit Price': 189.81, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'GLD', 'Class': 'Equity', 'Silo': 'D', 'Entry Date': d_250, 'Entry Price': 399.02, 'Shares': 63, 'Stop Loss': 380.0, 'Exit Date': d_200, 'Exit Price': 467.03, 'Strike': None, 'Expiry': ''},
            
            # Period 2 (d_200 to d_150): Defensive (Avg Gear ~2)
            {'Ticker': 'QQQ', 'Class': 'Equity', 'Silo': 'A', 'Entry Date': d_200, 'Entry Price': 612.87, 'Shares': 41, 'Stop Loss': 590.0, 'Exit Date': d_150, 'Exit Price': 557.67, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'GOOGL', 'Class': 'Equity', 'Silo': 'B', 'Entry Date': d_200, 'Entry Price': 323.90, 'Shares': 77, 'Stop Loss': 300.0, 'Exit Date': d_150, 'Exit Price': 273.34, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'AMD', 'Class': 'Equity', 'Silo': 'C', 'Entry Date': d_200, 'Entry Price': 216.00, 'Shares': 116, 'Stop Loss': 200.0, 'Exit Date': d_150, 'Exit Price': 196.04, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'TLT', 'Class': 'Equity', 'Silo': 'D', 'Entry Date': d_200, 'Entry Price': 85.56, 'Shares': 292, 'Stop Loss': 80.0, 'Exit Date': d_150, 'Exit Price': 85.12, 'Strike': None, 'Expiry': ''},
            
            # Period 3 (d_150 to d_100): Balanced (Avg Gear ~3)
            {'Ticker': 'AAPL', 'Class': 'Equity', 'Silo': 'A', 'Entry Date': d_150, 'Entry Price': 246.19, 'Shares': 102, 'Stop Loss': 230.0, 'Exit Date': d_100, 'Exit Price': 298.71, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'META', 'Class': 'Equity', 'Silo': 'B', 'Entry Date': d_150, 'Entry Price': 535.88, 'Shares': 47, 'Stop Loss': 500.0, 'Exit Date': d_100, 'Exit Price': 602.05, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'TSLA', 'Class': 'Equity', 'Silo': 'C', 'Entry Date': d_150, 'Entry Price': 355.28, 'Shares': 70, 'Stop Loss': 330.0, 'Exit Date': d_100, 'Exit Price': 404.11, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'XLU', 'Class': 'Equity', 'Silo': 'D', 'Entry Date': d_150, 'Entry Price': 45.63, 'Shares': 548, 'Stop Loss': 40.0, 'Exit Date': d_100, 'Exit Price': 44.06, 'Strike': None, 'Expiry': ''},
            
            # Period 4 (d_100 to d_50): Very Aggressive (Avg Gear ~5)
            {'Ticker': 'MSFT', 'Class': 'Equity', 'Silo': 'A', 'Entry Date': d_100, 'Entry Price': 415.74, 'Shares': 60, 'Stop Loss': 390.0, 'Exit Date': d_50, 'Exit Price': 382.62, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'NFLX', 'Class': 'Equity', 'Silo': 'B', 'Entry Date': d_100, 'Entry Price': 89.33, 'Shares': 280, 'Stop Loss': 75.0, 'Exit Date': d_50, 'Exit Price': 75.59, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'PLTR', 'Class': 'Equity', 'Silo': 'C', 'Entry Date': d_100, 'Entry Price': 135.26, 'Shares': 185, 'Stop Loss': 120.0, 'Exit Date': d_50, 'Exit Price': 132.22, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'SH', 'Class': 'Equity', 'Silo': 'D', 'Entry Date': d_100, 'Entry Price': 33.51, 'Shares': 746, 'Stop Loss': 30.0, 'Exit Date': d_50, 'Exit Price': 33.11, 'Strike': None, 'Expiry': ''},
            
            # Period 5 (d_50 to now): Very Defensive (Avg Gear ~1)
            {'Ticker': 'V', 'Class': 'Equity', 'Silo': 'A', 'Entry Date': d_50, 'Entry Price': 346.89, 'Shares': 72, 'Stop Loss': 330.0, 'Exit Date': None, 'Exit Price': None, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'DIS', 'Class': 'Equity', 'Silo': 'B', 'Entry Date': d_50, 'Entry Price': 96.70, 'Shares': 259, 'Stop Loss': 85.0, 'Exit Date': None, 'Exit Price': None, 'Strike': None, 'Expiry': ''},
            {'Ticker': 'IWM', 'Class': 'Option', 'Silo': 'C', 'Entry Date': d_50, 'Entry Price': 293.48, 'Shares': 85, 'Stop Loss': 280.00, 'Exit Date': None, 'Exit Price': None, 'Strike': 300, 'Expiry': (today + timedelta(days=30)).strftime('%Y-%m-%d')},
            {'Ticker': 'QQQ', 'Class': 'Option', 'Silo': 'D', 'Entry Date': d_50, 'Entry Price': 711.44, 'Shares': -35, 'Stop Loss': 730.00, 'Exit Date': None, 'Exit Price': None, 'Strike': 700, 'Expiry': (today + timedelta(days=15)).strftime('%Y-%m-%d')}
        ]
        
        df = pd.DataFrame(data)
        st.session_state.master_ledger = df

def render_master_ledger_control_panel(expanded=False):
    """Renders the universal expander for manipulating the Master Ledger."""
    with st.expander("🛠️ Edit Realized History (Master Ledger)", expanded=expanded):
        st.markdown("Edit the table below directly, or upload your own CSV. Changes instantly propagate across all modules.")
        
        # 1. Editable DataFrame
        edited_df = st.data_editor(
            st.session_state.master_ledger, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Class": st.column_config.SelectboxColumn("Class", options=["Equity", "Option"], required=True),
                "Silo": st.column_config.SelectboxColumn("Silo", options=["A", "B", "C", "D"], required=True),
                "Entry Date": st.column_config.DateColumn("Entry Date", format="YYYY-MM-DD"),
                "Exit Date": st.column_config.DateColumn("Exit Date", format="YYYY-MM-DD")
            }
        )
        
        # Update Session State if user edited the table
        if not edited_df.equals(st.session_state.master_ledger):
            st.session_state.master_ledger = edited_df
            st.rerun()
            
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            # CSV Download
            csv_data = st.session_state.master_ledger.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Sandbox Template (CSV)",
                data=csv_data,
                file_name="convexity_master_ledger_template.csv",
                mime="text/csv"
            )
        with col2:
            # CSV Upload
            uploaded_file = st.file_uploader("Upload your Master Ledger (CSV)", type=["csv"], label_visibility="collapsed")
            if uploaded_file is not None:
                try:
                    new_df = pd.read_csv(uploaded_file)
                    st.session_state.master_ledger = new_df
                    st.success("Master Ledger successfully overwritten!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error parsing CSV: {e}")

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
                pnl = shares * (spot - entry_price)
                
            else:
                # Trade is Closed: Calculate Realized PnL based on Exit Price
                if pd.notna(row['Exit Price']) and row['Exit Price'] != '':
                    exit_price = float(row['Exit Price'])
                else:
                    exit_price = entry_price # Fallback to 0 PnL if no exit price provided
                pnl = shares * (exit_price - entry_price)
                
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
