"""
Reusable UI components for the F1 Tire Analysis App.
"""

import streamlit as st
from datetime import datetime

def render_header():
    """Render the main app header."""
    st.markdown('<p class="main-header">🏎️ Camber F1 - Tire Degradation Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="info-text">Professional Formula 1 tire performance modeling and analysis tool</p>', unsafe_allow_html=True)

def render_footer():
    """Render the app footer."""
    st.markdown("---")
    st.markdown(
        '<p class="footer">🏎️ Camber F1 - Professional Tire Degradation Analysis | Data provided by FastF1</p>',
        unsafe_allow_html=True
    )

def render_metric_card(title, value, help_text=None):
    """Render a metric card."""
    col = st.columns(1)[0]
    with col:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric(title, value, help=help_text)
        st.markdown('</div>', unsafe_allow_html=True)

def render_data_quality_banner(year, check_data_quality_func):
    """Display a prominent banner about data quality."""
    icon, message, score, color = check_data_quality_func(year)
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, {color}20 0%, {color}10 100%);
        border-left: 5px solid {color};
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid {color}40;
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">{icon}</div>
            <div style="flex-grow: 1;">
                <div style="font-weight: 600; color: {color};">Data Quality Alert</div>
                <div style="color: #cccccc;">{message}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.5rem; font-weight: 700; color: {color};">{score}%</div>
                <div style="font-size: 0.8rem; color: #888;">Quality Score</div>
            </div>
        </div>
        <div style="margin-top: 0.5rem; height: 4px; background: #333; border-radius: 2px;">
            <div style="width: {score}%; height: 100%; background: {color}; border-radius: 2px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    return score

def render_feature_availability(features_dict):
    """Display a table of available features."""
    st.markdown("### 📋 Available Data Features")
    
    col1, col2 = st.columns(2)
    cols = [col1, col2]
    
    feature_items = list(features_dict.items())
    items_per_col = len(feature_items) // 2 + 1
    
    for col_idx, col in enumerate(cols):
        with col:
            start_idx = col_idx * items_per_col
            end_idx = min((col_idx + 1) * items_per_col, len(feature_items))
            
            for feature, available in feature_items[start_idx:end_idx]:
                if available:
                    st.markdown(f"✅ {feature}")
                else:
                    st.markdown(f"❌ {feature}")

def render_sidebar_quality_indicator(driver, year, round_num, icon, score, color):
    """Render quality indicator in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div style="
        background: {color}20;
        border-radius: 5px;
        padding: 0.5rem;
        border: 1px solid {color};
    ">
        <div style="font-size: 0.8rem; color: {color}; font-weight: 600;">📊 CURRENT ANALYSIS</div>
        <div style="font-size: 0.7rem; color: #ccc;">{driver} - {year} R{round_num}</div>
        <div style="font-size: 0.7rem; color: {color};">Quality: {score}% {icon}</div>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar_config():
    """Render sidebar configuration panel."""
    with st.sidebar:
        st.image("https://www.formula1.com/etc/designs/fom-website/images/f1_logo.svg", width=200)
        st.markdown("## ⚙️ Configuration")
        
        input_method = st.radio(
            "Data Source",
            ["🎯 Quick Analysis", "📅 Race Calendar", "📁 Upload CSV"],
            help="Choose how to load data"
        )
        
        st.markdown("### 🔧 Model Parameters")
        
        with st.expander("Fuel Model", expanded=False):
            fuel_decay = st.slider(
                "Fuel Burn per Lap (kg)",
                min_value=1.0, max_value=4.0, value=2.5, step=0.1,
                help="Amount of fuel consumed per lap"
            )
            
            fuel_penalty = st.slider(
                "Time Penalty per kg (s)",
                min_value=0.01, max_value=0.1, value=0.035, step=0.005,
                help="Time loss per kg of fuel"
            )
        
        with st.expander("Degradation Model", expanded=False):
            max_degradation = st.slider(
                "Max Degradation for 0% Health (s)",
                min_value=1.0, max_value=5.0, value=2.5, step=0.1,
                help="Time loss at which tire health reaches 0%"
            )
            
            benchmark = st.selectbox(
                "Benchmark Method",
                ["fastest", "second_lap", "median"],
                help="Method to calculate fresh tire benchmark"
            )
        
        return input_method, fuel_decay, fuel_penalty, max_degradation, benchmark