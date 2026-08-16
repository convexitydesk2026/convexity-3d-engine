"""
=============================================================================
Script Name: auth_gate.py
Version: v1.0
Purpose: License validation and Developer Bypass. Halts Streamlit execution 
         if a valid license or dev key is not found.
=============================================================================
"""
import os
import streamlit as st

def verify_access():
    # 1. The Developer Bypass (Checks for your hidden file)
    # Using relative path since it runs in the same directory
    if os.path.exists(".estate_dev_key"):
        return True
        
    # 2. The Customer Paywall (We will connect this to LemonSqueezy later)
    # For now, it acts as a hard lock.
    
    st.markdown("""
    <div style='text-align: center; margin-top: 50px;'>
        <h1 style='color: #1e293b;'>🔒 Estate Master Architecture</h1>
        <p style='color: #64748b; font-size: 18px;'>Institutional License Required</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Please enter your Annual License Key to authenticate this machine.")
        license_key = st.text_input("License Key", type="password", placeholder="XXXX-XXXX-XXXX-XXXX")
        
        if st.button("Authenticate Terminal", use_container_width=True):
            if license_key == "TEMP_BETA_KEY":
                st.success("✅ License Validated! Please refresh the page.")
                # We will add SQLite saving logic here later
            else:
                st.error("❌ Invalid or Expired License Key. Please contact support.")
                
    # THIS IS THE MAGIC LINE: It stops the rest of the dashboard from loading!
    st.stop()