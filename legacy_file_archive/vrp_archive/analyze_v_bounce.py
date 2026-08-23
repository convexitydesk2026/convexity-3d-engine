#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import optuna
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

OPTUNA_DB = 'postgresql://postgres:iD9nqV7$YW$T$z8@localhost:5432/optuna_studies'
STUDY_NAME = 'v_bounce_statistical_hunt_v2'

def load_study_data():
    try:
        study = optuna.load_study(study_name=STUDY_NAME, storage=OPTUNA_DB)
        df = study.trials_dataframe()
        # Drop failed trials and severe penalties (to fix Z-axis scaling)
        df = df[df['state'] == 'COMPLETE']
        df = df[df['value'] > -1.0]
        return df
    except Exception as e:
        print(f"Error loading study: {e}")
        return pd.DataFrame()

def generate_charts(df):
    if df.empty:
        print("No completed trials found in study.")
        return
        
    output_dir = r'C:\ORB20\Scripts\Py_scripts\Optuna\v_bounce_charts'
    os.makedirs(output_dir, exist_ok=True)
    
    # Rename columns for cleaner charts
    # Optuna prepends 'params_' to hyperparameter columns
    rename_map = {col: col.replace('params_', '') for col in df.columns if col.startswith('params_')}
    rename_map['value'] = 'Score_Avg_PnL'
    df = df.rename(columns=rename_map)
    
    print(f"Generating charts from {len(df)} trials...")

    # Chart 1: Profitability Matrix (Trailing Stop vs Take Profit vs Score)
    if 'trailing_stop_pct' in df.columns and 'take_profit_pct' in df.columns:
        fig1 = px.scatter_3d(
            df, 
            x='trailing_stop_pct', 
            y='take_profit_pct', 
            z='Score_Avg_PnL',
            color='drop_threshold_pct',
            title='Profitability Matrix: Trailing Stop vs Take Profit',
            labels={'Score_Avg_PnL': 'Avg PnL per Trade'},
            color_continuous_scale='Viridis'
        )
        fig1.write_html(os.path.join(output_dir, 'chart1_profitability_matrix.html'))
        
    # Chart 2: Drop Severity vs Volume vs Score
    if 'drop_threshold_pct' in df.columns and 'volume_multiplier' in df.columns:
        fig2 = px.scatter_3d(
            df,
            x='drop_threshold_pct',
            y='volume_multiplier',
            z='Score_Avg_PnL',
            color='strict_trigger',
            title='Drop Severity & Volume vs Score (Colored by Strict Trigger)',
            labels={'Score_Avg_PnL': 'Avg PnL per Trade'},
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig2.write_html(os.path.join(output_dir, 'chart2_drop_vs_volume.html'))
        
    # Chart 3: Wait Time vs Hold Time vs Score
    if 'watchlist_days' in df.columns and 'max_hold_days' in df.columns:
        fig3 = px.scatter_3d(
            df,
            x='watchlist_days',
            y='max_hold_days',
            z='Score_Avg_PnL',
            color='min_trigger_body_pct',
            title='Wait Time vs Hold Time vs Score',
            labels={'Score_Avg_PnL': 'Avg PnL per Trade'},
            color_continuous_scale='Plasma'
        )
        fig3.write_html(os.path.join(output_dir, 'chart3_time_dynamics.html'))
        
    # Chart 4: Stock Price vs Market Cap vs Score
    if 'min_price' in df.columns and 'min_dollar_volume' in df.columns:
        fig4 = px.scatter_3d(
            df,
            x='min_price',
            y='min_dollar_volume',
            z='Score_Avg_PnL',
            color='use_trailing_stop',
            title='Price vs Liquidity (Colored by Trailing Stop Usage)',
            labels={
                'min_dollar_volume': 'Min Dollar Vol (Market Cap Proxy)',
                'Score_Avg_PnL': 'Avg PnL per Trade'
            },
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig4.write_html(os.path.join(output_dir, 'chart4_price_vs_liquidity.html'))
        
    # Chart 5: Top Drivers (Hold Days vs Gap Abort vs Score)
    if 'max_hold_days' in df.columns and 'entry_gap_abort_pct' in df.columns:
        fig5 = px.scatter_3d(
            df,
            x='max_hold_days',
            y='entry_gap_abort_pct',
            z='Score_Avg_PnL',
            color='require_stock_uptrend',
            title='Top Drivers: Hold Days vs Gap Abort (Colored by Uptrend Filter)',
            labels={
                'entry_gap_abort_pct': 'Max Allowed Gap Down %',
                'Score_Avg_PnL': 'Avg PnL per Trade'
            },
            color_discrete_sequence=px.colors.qualitative.Dark2
        )
        fig5.write_html(os.path.join(output_dir, 'chart5_top_drivers.html'))

    print(f"Charts successfully saved to {output_dir}")

if __name__ == "__main__":
    df = load_study_data()
    generate_charts(df)
