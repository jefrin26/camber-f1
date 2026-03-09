"""
Professional F1 Tire Degradation Analysis App
Integrated Streamlit application with all functionality in one place.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import fastf1
from pathlib import Path
import logging
import os
from datetime import datetime
import base64
from io import BytesIO

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

# Custom CSS
st.markdown("""
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
</style>
""", unsafe_allow_html=True)

# Initialize cache
CACHE_DIR = Path(__file__).parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

#===============================================================================
# TIRE MODEL FUNCTIONS
#===============================================================================

def calculate_fuel_correction_vectorized(df, fuel_decay_per_lap=2.5, time_penalty_per_kg=0.035):
    """Calculate fuel correction for entire DataFrame."""
    result_df = df.copy()
    
    if 'StintLength' not in result_df.columns:
        stint_lengths = result_df.groupby('Stint')['TyreLife'].transform('max')
        result_df['StintLength'] = stint_lengths
    
    laps_completed = result_df.get('TyreLife', result_df.get('LapNumber'))
    remaining_laps = (result_df['StintLength'] - laps_completed).clip(lower=0)
    fuel_penalty = remaining_laps * fuel_decay_per_lap * time_penalty_per_kg
    
    return result_df['LapTimeSeconds'] - fuel_penalty

def calculate_degradation_delta(df, fuel_decay_per_lap=2.5, time_penalty_per_kg=0.035, benchmark_method='fastest'):
    """Calculate degradation delta for each lap."""
    result_df = df.copy()
    
    if 'StintLength' not in result_df.columns:
        stint_lengths = result_df.groupby('Stint')['TyreLife'].transform('max')
        result_df['StintLength'] = stint_lengths
    
    result_df['CorrectedTime'] = calculate_fuel_correction_vectorized(
        result_df, fuel_decay_per_lap, time_penalty_per_kg
    )
    
    result_df['DegradationDelta'] = 0.0
    result_df['FreshTireBenchmark'] = 0.0
    
    for stint_num in result_df['Stint'].unique():
        stint_mask = result_df['Stint'] == stint_num
        stint_data = result_df[stint_mask]
        
        if benchmark_method == 'fastest':
            benchmark_time = stint_data['CorrectedTime'].min()
        elif benchmark_method == 'second_lap' and len(stint_data) >= 2:
            second_lap = stint_data[stint_data['TyreLife'] == 2]
            benchmark_time = second_lap['CorrectedTime'].iloc[0] if not second_lap.empty else stint_data['CorrectedTime'].min()
        else:
            benchmark_time = stint_data['CorrectedTime'].median()
        
        result_df.loc[stint_mask, 'FreshTireBenchmark'] = benchmark_time
        result_df.loc[stint_mask, 'DegradationDelta'] = (
            result_df.loc[stint_mask, 'CorrectedTime'] - benchmark_time
        )
    
    return result_df

def calculate_health_score(degradation_delta, max_degradation=2.5):
    """Convert degradation delta to health score percentage."""
    normalized = np.clip(degradation_delta / max_degradation, 0, 1)
    return (1 - normalized) * 100

def add_health_scores(df, max_degradation=2.5):
    """Add health scores to DataFrame."""
    result_df = df.copy()
    result_df['HealthScore'] = result_df['DegradationDelta'].apply(
        lambda x: calculate_health_score(x, max_degradation)
    )
    return result_df

def calculate_stint_statistics(df):
    """Calculate per-stint statistics."""
    stats = []
    
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        compound = stint_data['Compound'].iloc[0] if len(stint_data) > 0 else 'Unknown'
        
        # Calculate degradation rate using linear regression
        if len(stint_data) >= 3:
            x = stint_data['TyreLife'].values.reshape(-1, 1)
            y = stint_data['DegradationDelta'].values
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(x, y)
            deg_rate = model.coef_[0]
        else:
            deg_rate = 0.0
        
        stint_stats = {
            'Stint': stint,
            'Compound': compound,
            'Laps': len(stint_data),
            'Avg Lap Time': round(stint_data['LapTimeSeconds'].mean(), 3),
            'Best Lap': round(stint_data['LapTimeSeconds'].min(), 3),
            'Avg Degradation': round(stint_data['DegradationDelta'].mean(), 3),
            'Max Degradation': round(stint_data['DegradationDelta'].max(), 3),
            'Degradation Rate (s/lap)': round(deg_rate, 4),
            'Avg Health %': round(stint_data['HealthScore'].mean(), 1),
            'Min Health %': round(stint_data['HealthScore'].min(), 1)
        }
        stats.append(stint_stats)
    
    return pd.DataFrame(stats)

#===============================================================================
# DATA FETCHER FUNCTIONS
#===============================================================================

@st.cache_data(ttl=3600, show_spinner="Fetching F1 data...")
def fetch_race_data(year, round_num, driver, session_type='R'):
    """Fetch race data for a specific driver."""
    try:
        session = fastf1.get_session(year, round_num, session_type)
        session.load()
        
        laps = session.laps.pick_drivers([driver])
        
        if len(laps) == 0:
            return None
        
        data = laps[['LapNumber', 'LapTime', 'Compound', 'Stint', 'TyreLife']].copy()
        data['LapTimeSeconds'] = data['LapTime'].apply(
            lambda x: x.total_seconds() if pd.notna(x) else None
        )
        data = data.dropna(subset=['LapTimeSeconds'])
        
        data['Year'] = year
        data['Round'] = round_num
        data['Driver'] = driver
        data['Session'] = session_type
        
        return data.reset_index(drop=True)
    
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

@st.cache_data(ttl=3600)
def get_available_races():
    """Get list of available races from FastF1."""
    try:
        current_year = datetime.now().year
        years = list(range(2018, current_year + 1))
        
        race_schedule = []
        for year in years:
            try:
                events = fastf1.get_event_schedule(year)
                for _, event in events.iterrows():
                    race_schedule.append({
                        'Year': year,
                        'Round': event['RoundNumber'],
                        'Event': event['EventName'],
                        'Country': event['Country'],
                        'Date': event['EventDate']
                    })
            except:
                continue
        
        return pd.DataFrame(race_schedule)
    except Exception as e:
        st.warning(f"Could not fetch race schedule: {e}")
        return pd.DataFrame()

#===============================================================================
# VISUALIZATION FUNCTIONS
#===============================================================================

def create_degradation_chart(df):
    """Create tire degradation visualization."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Lap Times by Stint', 'Tire Degradation (Delta)',
                       'Tire Health Score', 'Compound Performance Comparison'),
        vertical_spacing=0.12,
        horizontal_spacing=0.15
    )
    
    colors = {'SOFT': '#e10600', 'MEDIUM': '#ffd700', 'HARD': '#c0c0c0', 'INTERMEDIATE': '#228b22', 'WET': '#4169e1'}
    
    # 1. Lap Times
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        compound = stint_data['Compound'].iloc[0]
        color = colors.get(compound, '#808080')
        
        fig.add_trace(
            go.Scatter(
                x=stint_data['TyreLife'], 
                y=stint_data['LapTimeSeconds'],
                mode='lines+markers',
                name=f'Stint {stint} ({compound})',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                hovertemplate='Lap %{x}<br>Time: %{y:.3f}s<extra></extra>'
            ),
            row=1, col=1
        )
    
    # 2. Degradation Delta
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        compound = stint_data['Compound'].iloc[0]
        color = colors.get(compound, '#808080')
        
        fig.add_trace(
            go.Scatter(
                x=stint_data['TyreLife'], 
                y=stint_data['DegradationDelta'],
                mode='lines+markers',
                name=f'Stint {stint}',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                showlegend=False,
                hovertemplate='Lap %{x}<br>Delta: %{y:.3f}s<extra></extra>'
            ),
            row=1, col=2
        )
    
    # 3. Health Score
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        compound = stint_data['Compound'].iloc[0]
        color = colors.get(compound, '#808080')
        
        fig.add_trace(
            go.Scatter(
                x=stint_data['TyreLife'], 
                y=stint_data['HealthScore'],
                mode='lines+markers',
                name=f'Stint {stint}',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                showlegend=False,
                hovertemplate='Lap %{x}<br>Health: %{y:.1f}%<extra></extra>'
            ),
            row=2, col=1
        )
    
    # 4. Box plot by compound
    for compound in df['Compound'].unique():
        compound_data = df[df['Compound'] == compound]
        color = colors.get(compound, '#808080')
        
        fig.add_trace(
            go.Box(
                y=compound_data['LapTimeSeconds'],
                name=compound,
                marker_color=color,
                boxmean='sd',
                hovertemplate='Compound: %{y:.3f}s<extra></extra>'
            ),
            row=2, col=2
        )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.05,
            bgcolor="rgba(0,0,0,0.5)"
        ),
        paper_bgcolor='#0e1117',
        plot_bgcolor='#1e1e1e',
        font=dict(color='#ffffff'),
        title={
            'text': f"Tire Degradation Analysis - {df['Driver'].iloc[0]} ({df['Year'].iloc[0]} Round {df['Round'].iloc[0]})",
            'y':0.98,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=20, color='#e10600')
        }
    )
    
    # Update axes
    fig.update_xaxes(title_text="Tyre Life (Laps)", gridcolor='#333333', row=1, col=1)
    fig.update_xaxes(title_text="Tyre Life (Laps)", gridcolor='#333333', row=1, col=2)
    fig.update_xaxes(title_text="Tyre Life (Laps)", gridcolor='#333333', row=2, col=1)
    fig.update_xaxes(title_text="Compound", gridcolor='#333333', row=2, col=2)
    
    fig.update_yaxes(title_text="Lap Time (seconds)", gridcolor='#333333', row=1, col=1)
    fig.update_yaxes(title_text="Degradation Delta (seconds)", gridcolor='#333333', row=1, col=2)
    fig.update_yaxes(title_text="Tire Health (%)", gridcolor='#333333', row=2, col=1)
    fig.update_yaxes(title_text="Lap Time (seconds)", gridcolor='#333333', row=2, col=2)
    
    fig.add_hline(y=0, line_dash="dash", line_color="#e10600", opacity=0.3, row=1, col=2)
    
    return fig

def create_heatmap(df):
    """Create degradation heatmap."""
    pivot_data = df.pivot_table(
        values='DegradationDelta',
        index='Stint',
        columns='TyreLife',
        aggfunc='mean'
    ).fillna(0)
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='RdYlGn_r',
        text=np.round(pivot_data.values, 2),
        texttemplate='%{text}',
        textfont={"size": 10},
        hoverongaps=False,
        colorbar=dict(title="Degradation (s)")
    ))
    
    fig.update_layout(
        title="Degradation Heatmap by Stint",
        xaxis_title="Tyre Life (Laps)",
        yaxis_title="Stint",
        height=400,
        paper_bgcolor='#0e1117',
        plot_bgcolor='#1e1e1e',
        font=dict(color='#ffffff')
    )
    
    return fig

#===============================================================================
# EXPORT FUNCTIONS
#===============================================================================

def get_table_download_link(df, filename, text):
    """Generate download link for dataframe."""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv" style="color: #e10600;">📥 {text}</a>'
    return href

#===============================================================================
# MAIN APP
#===============================================================================

def main():
    # Header
    st.markdown('<p class="main-header">🏎️ Camber F1 - Tire Degradation Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="info-text">Professional Formula 1 tire performance modeling and analysis tool</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://www.formula1.com/etc/designs/fom-website/images/f1_logo.svg", width=200)
        st.markdown("## ⚙️ Configuration")
        
        # Input method selection
        input_method = st.radio(
            "Data Source",
            ["🎯 Quick Analysis", "📅 Race Calendar", "📁 Upload CSV"],
            help="Choose how to load data"
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
    
    # Main content area
    df = None
    
    # Handle different input methods
    if input_method == "🎯 Quick Analysis":
        st.markdown('<p class="sub-header">🎯 Quick Analysis</p>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            year = st.number_input("Year", min_value=2018, max_value=2024, value=2023)
        with col2:
            round_num = st.number_input("Round", min_value=1, max_value=24, value=22)
        with col3:
            driver = st.text_input("Driver Code", value="VER").upper()
        
        session = st.selectbox("Session", ["R", "Q", "S", "FP1", "FP2", "FP3"])
        
        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            with st.spinner("Fetching and analyzing data..."):
                raw_df = fetch_race_data(year, round_num, driver, session)
                
                if raw_df is not None and len(raw_df) > 0:
                    df = calculate_degradation_delta(raw_df, fuel_decay, fuel_penalty, benchmark)
                    df = add_health_scores(df, max_degradation)
                    st.session_state['analysis_df'] = df
                    st.success(f"✅ Analysis complete! Loaded {len(df)} laps.")
                else:
                    st.error("❌ No data found for the selected criteria.")
    
    elif input_method == "📅 Race Calendar":
        st.markdown('<p class="sub-header">📅 Race Calendar</p>', unsafe_allow_html=True)
        
        races_df = get_available_races()
        
        if not races_df.empty:
            years = sorted(races_df['Year'].unique(), reverse=True)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                selected_year = st.selectbox("Year", years)
            with col2:
                year_races = races_df[races_df['Year'] == selected_year]
                selected_race = st.selectbox(
                    "Race",
                    year_races.apply(lambda x: f"Round {x['Round']}: {x['Event']}", axis=1)
                )
                round_num = year_races.iloc[selected_race]['Round']
            with col3:
                driver = st.text_input("Driver Code", value="VER").upper()
            
            session = st.selectbox("Session", ["R", "Q", "S", "FP1", "FP2", "FP3"])
            
            if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
                with st.spinner("Fetching and analyzing data..."):
                    raw_df = fetch_race_data(selected_year, round_num, driver, session)
                    
                    if raw_df is not None and len(raw_df) > 0:
                        df = calculate_degradation_delta(raw_df, fuel_decay, fuel_penalty, benchmark)
                        df = add_health_scores(df, max_degradation)
                        st.session_state['analysis_df'] = df
                        st.success(f"✅ Analysis complete! Loaded {len(df)} laps.")
                    else:
                        st.error("❌ No data found for the selected criteria.")
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
                
                # Validate columns
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
            
            # Main degradation chart
            fig = create_degradation_chart(df)
            st.plotly_chart(fig, use_container_width=True)
            
            # Heatmap
            st.markdown('<p class="sub-header">🔥 Degradation Heatmap</p>', unsafe_allow_html=True)
            heatmap = create_heatmap(df)
            st.plotly_chart(heatmap, use_container_width=True)
        
        with tab3:
            st.markdown('<p class="sub-header">🔍 Detailed Lap Data</p>', unsafe_allow_html=True)
            
            # Filters
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
            
            # Apply filters
            filtered_df = df[
                (df['Stint'].isin(selected_stints)) &
                (df['Compound'].isin(selected_compounds)) &
                (df['HealthScore'] >= health_threshold)
            ]
            
            # Display data
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
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Lap-Level Data")
                st.markdown(get_table_download_link(
                    df, 
                    f"f1_tire_analysis_{df['Driver'].iloc[0]}_{df['Year'].iloc[0]}_R{df['Round'].iloc[0]}_laps",
                    "Download Lap Data (CSV)"
                ), unsafe_allow_html=True)
                
                st.markdown("### Stint Statistics")
                stint_stats = calculate_stint_statistics(df)
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
                    
                    SUMMARY STATISTICS
                    ------------------
                    Total Laps: {len(df)}
                    Number of Stints: {df['Stint'].nunique()}
                    Compounds Used: {', '.join(df['Compound'].unique())}
                    
                    Best Lap: {df['LapTimeSeconds'].min():.3f}s
                    Average Lap: {df['LapTimeSeconds'].mean():.3f}s
                    
                    Average Tire Health: {df['HealthScore'].mean():.1f}%
                    Average Degradation: {df['DegradationDelta'].mean():.3f}s
                    
                    STINT BREAKDOWN
                    ---------------
                    {calculate_stint_statistics(df).to_string()}
                    """
                    
                    b64 = base64.b64encode(summary.encode()).decode()
                    href = f'<a href="data:file/txt;base64,{b64}" download="analysis_report.txt" style="color: #e10600;">📥 Download Summary Report</a>'
                    st.markdown(href, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #666;">🏎️ Camber F1 - Professional Tire Degradation Analysis | Data provided by FastF1</p>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()