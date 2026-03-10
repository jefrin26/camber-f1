"""
UI styling components for the F1 Tire Analysis App.
"""

import streamlit as st

def load_css():
    """Load custom CSS styles."""
    return st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #e10600;
            font-weight: 700;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.5rem;
            color: #ffffff;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e10600;
        }
        .metric-card {
            background-color: #1e1e1e;
            border-radius: 10px;
            padding: 1rem;
            border-left: 4px solid #e10600;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        .info-text {
            color: #cccccc;
            font-size: 0.9rem;
        }
        .stDataFrame {
            background-color: #1e1e1e;
        }
        .quality-banner {
            padding: 1rem;
            border-radius: 5px;
            margin: 1rem 0;
            border-left: 5px solid;
        }
        .footer {
            text-align: center;
            color: #666;
            padding: 1rem;
        }
        .mode-toggle-container {
            background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
            border: 1px solid #e10600;
        }
        .mode-label {
            font-size: 0.9rem;
            color: #888;
            margin-bottom: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)
