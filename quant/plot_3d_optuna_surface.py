# ==============================================================================
# File: C:/Users/donca/Desktop/Desktop HP Envy x360 al 22Abr24/Docs Manuel/IBKR_Options/quant/plot_3d_optuna_surface.py
# Description: Generates a 3D Scatter Plot with a Surface Interpolation Mesh.
#              Dynamically reads the study name from the .ini file and handles
#              string-to-numeric conversions for categorical variables.
# Dependencies: pip install scipy plotly pandas optuna
# ==============================================================================

import configparser
import optuna
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import griddata
import webbrowser
import os

PROJECT_DIR = r"C:\Users\donca\Desktop\Desktop HP Envy x360 al 22Abr24\Docs Manuel\IBKR_Options\quant"
DB_CONFIG_PATH = r"C:\ORB20\Scripts\Py_scripts\DB_upload_config.ini"
OPTUNA_CONFIG_PATH = os.path.join(PROJECT_DIR, "optimizer_config_7_5x_ATR.ini")

def plot_3d_surface():
    # 1. Connect to Optuna DB
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH)
    creds = config['database']
    optuna_url = f"postgresql+psycopg2://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/optuna_studies"
    
    # 2. Get Study Name dynamically from the .ini file
    opt_config = configparser.ConfigParser()
    opt_config.read(OPTUNA_CONFIG_PATH)
    study_name = opt_config.get('Study', 'name')
    
    print(f"Connecting to database to plot study: {study_name}...")
    
    try:
        study = optuna.load_study(study_name=study_name, storage=optuna_url)
    except KeyError:
        print(f"\nERROR: The study '{study_name}' does not exist in the database yet!")
        print("Please ensure the engine script has successfully started and created the study.")
        return
    
    # 3. Extract Data
    trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not trials:
        print("No completed trials found in this study yet. Let the engine run a bit longer!")
        return

    data = []
    for t in trials:
        row = {'Trial': t.number, 'Calmar_Ratio': t.value}
        row.update(t.params)
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # --- FIX: Force numeric types so numpy can build the 3D spatial grid ---
    df['entry_time'] = pd.to_numeric(df['entry_time'], errors='coerce')
    df['atr_target'] = pd.to_numeric(df['atr_target'], errors='coerce')
    df['Calmar_Ratio'] = pd.to_numeric(df['Calmar_Ratio'], errors='coerce')
    
    # Drop any rows that failed conversion just to be safe
    df.dropna(subset=['entry_time', 'atr_target', 'Calmar_Ratio'], inplace=True)
    
    # 4. Prepare data for the Surface Mesh
    x = df['entry_time'].values
    y = df['atr_target'].values
    z = df['Calmar_Ratio'].values
    
    # Create a grid for interpolation
    xi = np.linspace(x.min(), x.max(), 50)
    yi = np.linspace(y.min(), y.max(), 50)
    X, Y = np.meshgrid(xi, yi)
    
    # Interpolate Z values over the grid
    Z = griddata((x, y), z, (X, Y), method='cubic')
    
    # 5. Build the Plotly Figure
    fig = go.Figure()

    # Add the Surface Mesh
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z, 
        colorscale='Viridis', 
        opacity=0.6,
        name='Interpolated Surface',
        showscale=False
    ))

    # Add the individual Scatter Dots
    fig.add_trace(go.Scatter3d(
        x=df['entry_time'], 
        y=df['atr_target'], 
        z=df['Calmar_Ratio'],
        mode='markers',
        marker=dict(
            size=5,
            color=df['Calmar_Ratio'], 
            colorscale='Turbo',
            showscale=True,
            colorbar=dict(title='Calmar Ratio')
        ),
        text=df['trailing_sma'],
        hovertemplate="<b>Entry Time:</b> %{x}m<br><b>ATR Target:</b> %{y}<br><b>Calmar:</b> %{z:.4f}<br><b>SMA:</b> %{text}<extra></extra>",
        name='Trials'
    ))
    
    fig.update_layout(
        title=f"3D Surface Optimization Landscape: {study_name}",
        template="plotly_dark",
        scene=dict(
            xaxis_title="Entry Time (Mins from Open)",
            yaxis_title="ATR Target Threshold",
            zaxis_title="Calmar Ratio (Score)"
        ),
        height=900
    )
    
    out_path = os.path.join(os.getcwd(), "optuna_3d_surface.html")
    fig.write_html(out_path)
    print(f"Done! 3D Surface Plot saved to: {out_path}")
    
    try:
        webbrowser.open(f'file://{os.path.realpath(out_path)}')
    except Exception:
        pass

if __name__ == "__main__":
    plot_3d_surface()