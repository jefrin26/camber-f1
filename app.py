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
    get_feature_availability,
    get_drivers_for_race
)

# Import live modules
from live import (
    LiveMonitor,
    render_live_header,
    render_driver_cards,
    create_live_chart,
    render_live_table,
    render_live_controls
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

#===============================================================================
# SIDEBAR CONFIGURATION (Override the one from ui.components to add cache management)
#===============================================================================

def render_sidebar_with_cache():
    """Render sidebar with cache management."""
    with st.sidebar:
        st.image("https://www.formula1.com/etc/designs/fom-website/images/f1_logo.svg", width=200)
        st.markdown("## ⚙️ Configuration")
        
        # Mode Toggle - Historical vs Live
        st.markdown("### 🎛️ Analysis Mode")
        
        # Initialize mode in session state if not present
        if 'analysis_mode' not in st.session_state:
            st.session_state['analysis_mode'] = 'historical'
        
        # Use segmented control for mode selection (available in newer Streamlit)
        try:
            analysis_mode = st.segmented_control(
                "Select Mode",
                options=["📅 Historical", "📡 Live"],
                default="📅 Historical" if st.session_state['analysis_mode'] == 'historical' else "📡 Live",
                help="Choose between historical race analysis or live monitoring",
                label_visibility="collapsed"
            )
        except AttributeError:
            # Fallback for older Streamlit versions
            analysis_mode = st.radio(
                "Select Mode",
                ["📅 Historical", "📡 Live"],
                index=0 if st.session_state['analysis_mode'] == 'historical' else 1,
                horizontal=True,
                help="Choose between historical race analysis or live monitoring"
            )
        
        # Extract mode from selection
        if analysis_mode == "📡 Live":
            st.session_state['analysis_mode'] = 'live'
        else:
            st.session_state['analysis_mode'] = 'historical'
        
        # Race Calendar is the default data source
        input_method = "📅 Race Calendar"
        
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
        
        # New Analysis button
        if st.button("🔄 New Analysis", use_container_width=True):
            if 'analysis_df' in st.session_state:
                del st.session_state['analysis_df']
            st.rerun()
        
        # Live Monitoring Configuration
        st.markdown("### 📡 Live Monitoring")
        
        with st.expander("Live Settings", expanded=True):
            live_drivers = st.multiselect(
                "Drivers to Monitor",
                ['VER', 'HAM', 'NOR', 'LEC', 'PIA', 'RUS', 'ALO', 'GAS', 'TSU', 'BOT', 
                 'ZHO', 'ALB', 'OCO', 'STR', 'MAG', 'HUL', 'DEV', 'SAI', 'PER', 'RIC'],
                default=['VER', 'HAM', 'LEC'],
                help="Select drivers to monitor in live mode"
            )
            
            live_session = st.selectbox(
                "Live Session",
                ["R", "Q", "S", "FP1", "FP2", "FP3"],
                index=0,
                help="Session type for live monitoring"
            )
        
        return input_method, fuel_decay, fuel_penalty, max_degradation, benchmark, live_drivers, live_session

#===============================================================================
# MAIN APP
#===============================================================================

def main():
    # Render header
    render_header()
    
    # Render sidebar with cache management and get configuration
    input_method, fuel_decay, fuel_penalty, max_degradation, benchmark, live_drivers, live_session = render_sidebar_with_cache()
    
    # Store live settings in session state
    st.session_state['live_drivers'] = live_drivers
    st.session_state['live_session'] = live_session
    
    # Get current mode
    mode = st.session_state.get('analysis_mode', 'historical')
    
    #===============================================================================
    # HISTORICAL ANALYSIS MODE
    #===============================================================================
    
    if mode == 'historical':
        
        # Main content area
        df = None
        
        # Race Calendar is the only data source
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
                
                # Find the index of Round 1 (default to 0 if not found)
                round_1_idx = 0
                for idx, option in enumerate(race_options):
                    if 'Round 1:' in option:
                        round_1_idx = idx
                        break
                
                selected_race = st.selectbox("Race", race_options, index=round_1_idx, key="calendar_race")
                selected_idx = race_options.index(selected_race)
                round_num = int(year_races.iloc[selected_idx]['Round'])
            
            # Session selection before driver (needed for driver list)
            session = st.selectbox("Session", ["R", "Q", "S", "FP1", "FP2", "FP3"], key="calendar_session")
            
            with col3:
                # Fetch drivers for the selected race
                drivers_list = get_drivers_for_race(selected_year, round_num, session)
                
                # If no drivers found (empty list), use a fallback list of common F1 drivers
                if not drivers_list:
                    drivers_list = ['VER', 'HAM', 'NOR', 'LEC', 'PIA', 'RUS', 'ALO', 'GAS', 'TSU', 'BOT', 'ZHO', 'ALB', 'OCO', 'STR', 'MAG', 'HUL', 'DEV', 'SAI', 'PER', 'RIC']
                    st.warning(f"⚠️ Could not fetch drivers for this race. Showing common drivers.")
                
                driver = st.selectbox("Driver", drivers_list, index=drivers_list.index('VER') if 'VER' in drivers_list else 0, key="calendar_driver")
            
            if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
                if quality_score < 20:
                    st.error("❌ Selected year has very limited data.")
                    if not st.checkbox("Continue anyway?"):
                        st.stop()
                
                with st.spinner("Fetching and analyzing data..."):
                    # Clear cache before fetching new data to ensure fresh results
                    clear_all_cache()
                    
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
            st.warning("Could not load race calendar.")
        
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
    
    #===============================================================================
    # LIVE MONITORING MODE
    #===============================================================================
    
    else:
        st.markdown('<p class="sub-header">📡 Live Tire Monitoring</p>', unsafe_allow_html=True)
        
        # Initialize live monitor in session state
        if 'live_monitor' not in st.session_state:
            st.session_state['live_monitor'] = LiveMonitor()
        
        monitor = st.session_state['live_monitor']
        
        # Live controls
        start, pause, resume, stop, refresh = render_live_controls()
        
        # Handle control actions
        if start:
            # Get parameters from sidebar
            params = {
                'fuel_decay': fuel_decay,
                'fuel_penalty': fuel_penalty,
                'max_degradation': max_degradation,
                'benchmark': benchmark
            }
            
            # Use selected drivers or default
            drivers = st.session_state.get('live_drivers', ['VER', 'HAM', 'LEC'])
            session = st.session_state.get('live_session', 'R')
            
            monitor.start(drivers, session, params, update_interval=15)
            st.rerun()
        
        elif pause:
            monitor.pause()
            st.rerun()
        
        elif resume:
            monitor.resume()
            st.rerun()
        
        elif stop:
            monitor.stop()
            st.rerun()
        
        elif refresh:
            monitor.update()
            st.rerun()
        
        # Display live monitoring interface
        if monitor.is_active or monitor.processed_data is not None:
            # Show header with status
            render_live_header(monitor)
            
            # Show driver cards
            if monitor.driver_stats:
                render_driver_cards(monitor.driver_stats, monitor.trends)
            
            # Show live chart
            if monitor.processed_data is not None:
                fig = create_live_chart(monitor.processed_data)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Show live data table
                with st.expander("📋 Live Data Table", expanded=False):
                    render_live_table(monitor.processed_data)
            
            # Auto-refresh if active
            if monitor.is_active and not monitor.is_paused:
                time.sleep(monitor.update_interval)
                st.rerun()
        else:
            st.info("👈 Configure live monitoring in the sidebar and click 'Start'")
    
    # Render footer
    render_footer()

if __name__ == "__main__":
    main()

