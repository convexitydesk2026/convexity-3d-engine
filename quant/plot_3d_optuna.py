# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/plot_3d_optuna.py
# Description: Generates an interactive 3D Scatter Plot of Optuna Trials.
# ==============================================================================

import configparser
import optuna
import pandas as pd
import plotly.express as px
import webbrowser
import os

DB_CONFIG_PATH = r"C:\ORB20\Scripts\Py_scripts\DB_upload_config.ini"
STUDY_NAME = "ORB20-ADAPT_Champion_Swing_FINAL_9YR" # Change this to the study you want to view

def plot_3d():
    # 1. Connect to Optuna DB
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH)
    creds = config['database']
    optuna_url = f"postgresql+psycopg2://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/optuna_studies"
    
    study = optuna.load_study(study_name=STUDY_NAME, storage=optuna_url)
    
    # 2. Extract Data
    trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if len(trials) == 0:
        print("No completed trials found in this study.")
        return

    data = []
    for t in trials:
        row = {'Trial': t.number, 'Calmar_Ratio': t.value}
        row.update(t.params)
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # 3. Create 3D Plot
    # X = Entry Time | Y = ATR Target | Z = Calmar Ratio | Color = Trailing SMA
    fig = px.scatter_3d(df, x='entry_time', y='atr_target', z='Calmar_Ratio',
                        color='trailing_sma', hover_data=['Trial', 'transition_r', 'max_positions', 'atr_padding'],
                        title=f"3D Optimization Landscape: {STUDY_NAME}",
                        color_discrete_sequence=px.colors.qualitative.Plotly)
    
    fig.update_layout(template="plotly_dark", scene=dict(zaxis_title="Calmar Ratio (Score)"))
    
    out_path = os.path.join(os.getcwd(), "optuna_3d_landscape.html")
    fig.write_html(out_path)
    print(f"Done! 3D Plot saved to: {out_path}")
    webbrowser.open(f'file://{os.path.realpath(out_path)}')

if __name__ == "__main__":
    plot_3d()