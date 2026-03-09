"""
Export functionality for the F1 Tire Analysis App.
"""

import streamlit as st
import base64
import pandas as pd
from datetime import datetime

def get_table_download_link(df, filename, text):
    """Generate download link for dataframe."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv" style="color: #e10600;">📥 {text}</a>'
    return href

def render_export_section(df, stint_stats, icon, message, score):
    """Render the export tab content."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Lap-Level Data")
        st.markdown(get_table_download_link(
            df, 
            f"f1_tire_analysis_{df['Driver'].iloc[0]}_{df['Year'].iloc[0]}_R{df['Round'].iloc[0]}_laps",
            "Download Lap Data (CSV)"
        ), unsafe_allow_html=True)
        
        st.markdown("### Stint Statistics")
        st.markdown(get_table_download_link(
            stint_stats,
            f"f1_tire_analysis_{df['Driver'].iloc[0]}_{df['Year'].iloc[0]}_R{df['Round'].iloc[0]}_stints",
            "Download Stint Stats (CSV)"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown("### Summary Report")
        if st.button("Generate Summary Report", use_container_width=True):
            summary = f"""
            F1 TIRE DEGRADATION ANALYSIS REPORT
            ====================================
            Driver: {df['Driver'].iloc[0]}
            Year: {df['Year'].iloc[0]}
            Round: {df['Round'].iloc[0]}
            Session: {df['Session'].iloc[0]}
            Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            DATA QUALITY: {score}% {icon}
            {message}
            
            SUMMARY STATISTICS
            ------------------
            Total Laps: {len(df)}
            Number of Stints: {df['Stint'].nunique()}
            Compounds Used: {', '.join(df['Compound'].unique()) if df['Compound'].notna().any() else 'N/A'}
            
            Best Lap: {df['LapTimeSeconds'].min():.3f}s
            Average Lap: {df['LapTimeSeconds'].mean():.3f}s
            
            Average Tire Health: {df['HealthScore'].mean():.1f}%
            Average Degradation: {df['DegradationDelta'].mean():.3f}s
            
            STINT BREAKDOWN
            ---------------
            {stint_stats.to_string()}
            
            NOTE: Analysis quality depends on data availability for the selected year.
            """
            
            b64 = base64.b64encode(summary.encode()).decode()
            href = f'<a href="data:file/txt;base64,{b64}" download="analysis_report.txt" style="color: #e10600;">📥 Download Summary Report</a>'
            st.markdown(href, unsafe_allow_html=True)