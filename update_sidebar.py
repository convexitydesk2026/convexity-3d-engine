import sys
with open('dashboard_pro_v188.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if 'st.markdown("### 📌 Institutional Directory")' in line:
        start_idx = i + 2
    if start_idx != -1 and i > start_idx and 'st.markdown("---")' in line:
        end_idx = i - 2
        break

if start_idx != -1 and end_idx != -1:
    new_sidebar = '''    - [Estate Master Dashboard](#top)
    - [Master Estate Aggregation](#master-agg)
    - [Estate Calendars](#sec1b)
      - [Monthly / YTD Return Heatmap](#sec1b)
      - [Daily PnL](#sec1b)
      - [Unified Action Items](#sec1b)
    - [Global Market Flow & Institutional Rotation](#sec1c)
    - [Estate Breakdown](#sec1)
      - [GAAP Balance Sheet & Allocation](#sec1)
      - [Live Portfolio Composition](#sec2)
      - [Daily PnL Trajectory](#sec3)
      - [Physical Equity Risk Ledger](#sec3b)
      - [PnL Attribution & Capital Velocity](#sec4)
    - [Deployment Command Center (Transition to 60/40)](#sec5)
    - [Capital Deployment & Margin Capacity Tracker](#sec6)
    - [Advanced Portfolio Risk Metrics](#sec6b)
    - [S.W.A.N. Stress Test](#sec6c)
    - [Master Instrument Matrix (Tax, Alpha, & Sharpe Grading)](#sec7)
    - [Estate Montecarlo PnL Simulation](#sec8)
    - [Master Options Matrix & CFO Briefing](#sec9a)
    - [Options Performance Ledger & Topography Engine](#sec9b)
    - [Alpha Campaigns Accountability Journal](#sec10)
    - [Convexity Desk Project Management](#sec100)
    - [Convexity Desk Publisher Pipeline (Ghost.org)](#sec101)\n'''
    
    del lines[start_idx:end_idx+1]
    lines.insert(start_idx, new_sidebar)
    with open('dashboard_pro_v188.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Sidebar updated.")
else:
    print(f"Indices not found: start={start_idx}, end={end_idx}")

