import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from public_core_math import render_global_sidebar, render_page_footer, render_page_header, init_global_state

st.set_page_config(page_title="Glossary and References | Convexity Desk", layout="wide")

render_global_sidebar()
init_global_state()

render_page_header("📖 Glossary and References", "Key terms, mathematical methodologies, and reference material for the Convexity Engine.")
st.markdown("---")

st.info("Content pending.")

render_page_footer("The Convexity Desk Glossary defines institutional volatility terminology.")
