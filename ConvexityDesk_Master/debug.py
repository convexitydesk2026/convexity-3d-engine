import pandas as pd
import sys
sys.path.append('.')
from public_core_math import init_global_state, compute_daily_trajectory
import streamlit as st

class MockSessionState(dict):
    def __getattr__(self, name):
        return self[name]
    def __setattr__(self, name, value):
        self[name] = value

st.session_state = MockSessionState()
init_global_state()

df = compute_daily_trajectory(st.session_state.master_ledger)
df.to_csv(r'C:\Users\donca\.gemini\antigravity-ide\brain\a819ca6d-2d8c-4671-92f7-92485035e441\scratch\debug.csv', index=False)
