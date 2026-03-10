"""
Professional F1 Tire Degradation Analysis App
Master entrypoint - integrates all modules.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import time

# Import UI components
from ui import (
    load_css,
    render_header,
    render_footer,
    render_sidebar_config,
    render_data_quality_banner,
    render_feature_availability,
    render_sidebar_quality_indicator,
    render_export_section
)

# Import core modules
from src.tire_model import (
    calculate_degradation_delta,
    add_health_scores,
    calculate_stint_statistics,
    create_degradation_chart,
    create_heatmap
)

# Import cache manager
from src.cache_manager import (
    get_cache_size,
    clear_old_cache,
    clear_session_cache,
    clear_all_cache,
    list_cache_contents,
    get_cache_stats
)

# Import data fetcher (non-cache functions)
from src.data_fetcher import (
    fetch_race_data,
    get_available_races,
    check_data_quality,
    get_feature_availability
)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Camber F1 - Tire Degradation Analysis",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
load_css()

if 'confirm_clear_all' not in st.session_state:
    st.session_state['confirm_clear_all'] = False
if 'last_cache_action' not in st.session_state:
    st.session_state['last_cache_action'] = None
if 'cache_action_time' not in st.session_state:
    st.session_state['cache_action_time'] = None

#===============================================================================
# SIDEBAR CONFIGURATION (Override the one from ui.components to add cache management)
#===============================================================================

def render_sidebar_with_cache():
    """Render sidebar with cache management."""
    with st.sidebar:
        st.image("https://www.formula1.com/etc/designs/fom-website/images/f1_logo.svg", width=200)
        st.markdown("## ⚙️ Configuration")
        
        # Input method selection
        input_method = st.radio(
            "Data Source",
            ["🎯 Quick Analysis", "📅 Race Calendar", "📁 Upload CSV"],
            help="Choose how to load data",
            key="input_method"
        )
        
        # Analysis parameters
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
        
        # Cache management
        st.markdown("### 🗑️ Cache Management")
        with st.expander("Cache Settings", expanded=False):
            # Get cache info
            cache_info = get_cache_size()
            
            # Display cache stats
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Size", f"{cache_info['size_mb']:.1f} MB")
            with col2:
                st.metric("Files", cache_info['file_count'])
            
            # Show last action if any
            if st.session_state['cache_action_time']:
                st.caption(f"Last: {st.session_state['last_cache_action']} at {st.session_state['cache_action_time']}")
            
            # Cache action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear Temp", use_container_width=True, help="Clear temporary files (.npy, .tmp, etc.)"):
                    with st.spinner("Clearing temporary files..."):
                        deleted = clear_session_cache()
                        if deleted > 0:
                            st.session_state['last_cache_action'] = f"Cleared {deleted} temp files"
                            st.session_state['cache_action_time'] = datetime.now().strftime("%H:%M:%S")
                            st.success(f"✅ Cleared {deleted} temporary files!")
                        else:
                            st.info("No temporary files to clear")
                        time.sleep(1)
                        st.rerun()
            
            with col2:
                if st.button("🧹 Clear Old", use_container_width=True, help="Clear files older than 7 days"):
                    with st.spinner("Clearing old files..."):
                        deleted = clear_old_cache(max_age_days=7)
                        if deleted > 0:
                            st.session_state['last_cache_action'] = f"Cleared {deleted} old files"
                            st.session_state['cache_action_time'] = datetime.now().strftime("%H:%M:%S")
                            st.success(f"✅ Cleared {deleted} old files!")
                        else:
                            st.info("No old files to clear")
                        time.sleep(1)
                        st.rerun()
            
            # Clear all button with confirmation
            if st.button("⚠️ Clear All Cache", use_container_width=True, type="secondary", help="Delete everything in cache"):
                st.session_state['confirm_clear_all'] = True
            
            if st.session_state['confirm_clear_all']:
                st.warning("⚠️ This will delete ALL cached data!")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes, delete all", use_container_width=True, key="confirm_yes"):
                        with st.spinner("Deleting all cache..."):
                            before_info = get_cache_size()
                            result = clear_all_cache()
                            if result:
                                after_info = get_cache_size()
                                deleted_count = before_info['file_count'] - after_info['file_count']
                                st.session_state['last_cache_action'] = f"Cleared all ({deleted_count} files)"
                                st.session_state['cache_action_time'] = datetime.now().strftime("%H:%M:%S")
                                st.success(f"✅ Deleted {deleted_count} files! Cache is now {after_info['size_mb']:.1f} MB")
                            else:
                                st.error("❌ Failed to clear some files")
                            st.session_state['confirm_clear_all'] = False
                            time.sleep(1)
                            st.rerun()
                
                with col_no:
                    if st.button("❌ Cancel", use_container_width=True, key="confirm_no"):
                        st.session_state['confirm_clear_all'] = False
                        st.rerun()
            
            # Optional: Show cache contents (collapsible)
            with st.expander("📂 View Cache Contents", expanded=False):
                contents = list_cache_contents(limit=15)
                if contents:
                    for item in contents:
                        st.text(f"📄 {item['name']} ({item['size_kb']} KB)")
                    cache_info = get_cache_size()
                    if cache_info['file_count'] > 15:
                        st.text(f"... and {cache_info['file_count'] - 15} more files")
                else:
                    st.text("Cache is empty")
        
        # New Analysis button
        if st.button("🔄 New Analysis", use_container_width=True):
            if 'analysis_df' in st.session_state:
                del st.session_state['analysis_df']
            st.rerun()
        
        # Display cache size in sidebar footer
        cache_info = get_cache_size()
        st.sidebar.markdown("---")
        st.sidebar.caption(f"💾 Cache: {cache_info['size_mb']:.1f} MB ({cache_info['file_count']} files)")
        
        return input_method, fuel_decay, fuel_penalty, max_degradation, benchmark

#===============================================================================
# MAIN APP
#===============================================================================

def main():
    # Render header
    render_header()
    
    # Render sidebar with cache management and get configuration
    input_method, fuel_decay, fuel_penalty, max_degradation, benchmark = render_sidebar_with_cache()
    
    # Main content area
    df = None
    
    # Handle different input methods
    if input_method == "🎯 Quick Analysis":
        st.markdown('<p class="sub-header">🎯 Quick Analysis</p>', unsafe_allow_html=True)
        
        # Add a clear button in the main area too
        col_clear, col_empty = st.columns([1, 11])
        with col_clear:
            if st.button("🗑️ Clear Results", use_container_width=True):
                if 'analysis_df' in st.session_state:
                    del st.session_state['analysis_df']
                st.rerun()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            year = st.number_input("Year", min_value=1950, max_value=datetime.now().year, value=2023, key="quick_year")
        with col2:
            round_num = st.number_input("Round", min_value=1, max_value=30, value=22, key="quick_round")
        with col3:
            driver = st.text_input("Driver Code", value="VER", key="quick_driver").upper()
        
        # Display data quality banner
        quality_score = render_data_quality_banner(year, check_data_quality)
        
        # If older data, show additional warning
        if quality_score < 75:
            with st.expander("🔍 What data is available for this year?", expanded=True):
                render_feature_availability(get_feature_availability(year))
                
                if quality_score < 50:
                    st.warning("""
                    **⚠️ Analysis Limitations:**
                    - Tire compound data may not be available
                    - Fuel correction will be based on estimates
                    - Health scores will be calculated from lap times only
                    """)
        
        session = st.selectbox("Session", ["R", "Q", "S", "FP1", "FP2", "FP3"], key="quick_session")
        
        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            # Check year validity before running
            if quality_score < 20:
                st.error("❌ Selected year has very limited data. Analysis may not be meaningful.")
                if not st.checkbox("Continue anyway?"):
                    st.stop()
            
            with st.spinner("Fetching and analyzing data..."):
                raw_df = fetch_race_data(year, round_num, driver, session)
                
                if raw_df is not None and len(raw_df) > 0:
                    # Add year-specific warnings
                    if year < 2018:
                        st.warning(f"⚠️ **Note:** Data from {year} has limitations. Tire compound information may be incomplete.")
                    
                    df = calculate_degradation_delta(raw_df, fuel_decay, fuel_penalty, benchmark)
                    df = add_health_scores(df, max_degradation)
                    st.session_state['analysis_df'] = df
                    st.success(f"✅ Analysis complete! Loaded {len(df)} laps.")
                else:
                    st.error("❌ No data found for the selected criteria.")
    
    elif input_method == "📅 Race Calendar":
        st.markdown('<p class="sub-header">📅 Race Calendar</p>', unsafe_allow_html=True)
        
        # Add a clear button
        col_clear, col_empty = st.columns([1, 11])
        with col_clear:
            if st.button("🗑️ Clear Results", use_container_width=True):
                if 'analysis_df' in st.session_state:
                    del st.session_state['analysis_df']
                st.rerun()
        
        races_df = get_available_races()
        
        if not races_df.empty:
            years = sorted(races_df['Year'].unique(), reverse=True)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_year = st.selectbox("Year", years, key="calendar_year")
                quality_score = render_data_quality_banner(selected_year, check_data_quality)
                
                if quality_score < 75:
                    with st.expander("🔍 Available data for this year", expanded=False):
                        render_feature_availability(get_feature_availability(selected_year))
            
            with col2:
                year_races = races_df[races_df['Year'] == selected_year]
                race_options = year_races.apply(
                    lambda x: f"Round {int(x['Round'])}: {x['Event']} ({x['Country']})", 
                    axis=1
                ).tolist()
                
                selected_race = st.selectbox("Race", race_options, key="calendar_race")
                selected_idx = race_options.index(selected_race)
                round_num = int(year_races.iloc[selected_idx]['Round'])
            
            with col3:
                driver = st.text_input("Driver Code", value="VER", key="calendar_driver").upper()
            
            session = st.selectbox("Session", ["R", "Q", "S", "FP1", "FP2", "FP3"], key="calendar_session")
            
            if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
                if quality_score < 20:
                    st.error("❌ Selected year has very limited data.")
                    if not st.checkbox("Continue anyway?"):
                        st.stop()
                
                with st.spinner("Fetching and analyzing data..."):
                    raw_df = fetch_race_data(selected_year, round_num, driver, session)
                    
                    if raw_df is not None and len(raw_df) > 0:
                        if selected_year < 2018:
                            st.warning(f"⚠️ **Note:** Data from {selected_year} has limitations.")
                        
                        df = calculate_degradation_delta(raw_df, fuel_decay, fuel_penalty, benchmark)
                        df = add_health_scores(df, max_degradation)
                        st.session_state['analysis_df'] = df
                        st.success(f"✅ Analysis complete! Loaded {len(df)} laps.")
                    else:
                        st.error("❌ No data found.")
        else:
            st.warning("Could not load race calendar. Please use Quick Analysis.")
    
    else:  # Upload CSV
        st.markdown('<p class="sub-header">📁 Upload Your Data</p>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Upload CSV file with lap data",
            type=['csv'],
            help="File must contain columns: LapNumber, LapTimeSeconds, TyreLife, Stint, Compound"
        )
        
        if uploaded_file is not None:
            try:
                raw_df = pd.read_csv(uploaded_file)
                required_cols = ['LapNumber', 'LapTimeSeconds', 'TyreLife', 'Stint', 'Compound']
                
                if all(col in raw_df.columns for col in required_cols):
                    df = calculate_degradation_delta(raw_df, fuel_decay, fuel_penalty, benchmark)
                    df = add_health_scores(df, max_degradation)
                    st.session_state['analysis_df'] = df
                    st.success(f"✅ File loaded! Found {len(df)} laps.")
                else:
                    st.error(f"CSV must contain columns: {required_cols}")
            except Exception as e:
                st.error(f"Error loading file: {e}")
    
    # Display results if available
    if 'analysis_df' in st.session_state and st.session_state['analysis_df'] is not None:
        df = st.session_state['analysis_df']
        
        # Show data quality in sidebar
        year = df['Year'].iloc[0]
        icon, message, score, color = check_data_quality(year)
        render_sidebar_quality_indicator(df['Driver'].iloc[0], year, df['Round'].iloc[0], icon, score, color)
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Visualizations", "🔍 Detailed Data", "📥 Export"])
        
        with tab1:
            st.markdown('<p class="sub-header">📊 Analysis Overview</p>', unsafe_allow_html=True)
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Total Laps", len(df))
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("Stints", df['Stint'].nunique())
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                avg_health = df['HealthScore'].mean()
                st.metric("Avg Tire Health", f"{avg_health:.1f}%")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col4:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                best_lap = df['LapTimeSeconds'].min()
                st.metric("Best Lap", f"{best_lap:.3f}s")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Stint statistics
            st.markdown('<p class="sub-header">📈 Stint Statistics</p>', unsafe_allow_html=True)
            stint_stats = calculate_stint_statistics(df)
            st.dataframe(
                stint_stats,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Degradation Rate (s/lap)": st.column_config.NumberColumn(format="%.4f"),
                    "Avg Degradation": st.column_config.NumberColumn(format="%.3f"),
                    "Avg Health %": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            # Quick insights
            st.markdown('<p class="sub-header">💡 Key Insights</p>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                best_stint = stint_stats.loc[stint_stats['Avg Health %'].idxmax()]
                st.info(f"🏆 **Best Performing Stint**: Stint {best_stint['Stint']} ({best_stint['Compound']})\n\n"
                       f"- Average Health: {best_stint['Avg Health %']:.1f}%\n"
                       f"- Degradation Rate: {best_stint['Degradation Rate (s/lap)']:.4f} s/lap\n"
                       f"- Laps: {best_stint['Laps']}")
            
            with col2:
                worst_stint = stint_stats.loc[stint_stats['Max Degradation'].idxmax()]
                st.warning(f"⚠️ **Highest Degradation**: Stint {worst_stint['Stint']} ({worst_stint['Compound']})\n\n"
                          f"- Max Degradation: {worst_stint['Max Degradation']:.3f}s\n"
                          f"- Min Health: {worst_stint['Min Health %']:.1f}%\n"
                          f"- Degradation Rate: {worst_stint['Degradation Rate (s/lap)']:.4f} s/lap")
        
        with tab2:
            st.markdown('<p class="sub-header">📈 Tire Degradation Visualizations</p>', unsafe_allow_html=True)
            
            fig = create_degradation_chart(df)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('<p class="sub-header">🔥 Degradation Heatmap</p>', unsafe_allow_html=True)
            heatmap = create_heatmap(df)
            st.plotly_chart(heatmap, use_container_width=True)
        
        with tab3:
            st.markdown('<p class="sub-header">🔍 Detailed Lap Data</p>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_stints = st.multiselect(
                    "Filter by Stint",
                    options=sorted(df['Stint'].unique()),
                    default=sorted(df['Stint'].unique())
                )
            
            with col2:
                selected_compounds = st.multiselect(
                    "Filter by Compound",
                    options=df['Compound'].unique(),
                    default=df['Compound'].unique()
                )
            
            with col3:
                health_threshold = st.slider(
                    "Min Health Score",
                    min_value=0, max_value=100, value=0
                )
            
            filtered_df = df[
                (df['Stint'].isin(selected_stints)) &
                (df['Compound'].isin(selected_compounds)) &
                (df['HealthScore'] >= health_threshold)
            ]
            
            display_cols = ['LapNumber', 'TyreLife', 'Compound', 'Stint', 
                          'LapTimeSeconds', 'CorrectedTime', 'DegradationDelta', 'HealthScore']
            
            st.dataframe(
                filtered_df[display_cols].sort_values(['Stint', 'LapNumber']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "LapTimeSeconds": st.column_config.NumberColumn(format="%.3f s"),
                    "CorrectedTime": st.column_config.NumberColumn(format="%.3f s"),
                    "DegradationDelta": st.column_config.NumberColumn(format="%.3f s"),
                    "HealthScore": st.column_config.NumberColumn(format="%.1f %%")
                }
            )
            
            st.caption(f"Showing {len(filtered_df)} of {len(df)} laps")
        
        with tab4:
            st.markdown('<p class="sub-header">📥 Export Data</p>', unsafe_allow_html=True)
            stint_stats = calculate_stint_statistics(df)
            render_export_section(df, stint_stats, icon, message, score)
    
    # Render footer
    render_footer()

if __name__ == "__main__":
    main()