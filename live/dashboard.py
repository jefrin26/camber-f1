"""
Live dashboard UI components.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

def render_live_header(monitor):
    """Render live monitoring header with status."""
    status = monitor.get_status()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if status['active'] and not status['paused']:
            st.markdown("🟢 **LIVE**")
        elif status['paused']:
            st.markdown("🟡 **PAUSED**")
        else:
            st.markdown("⚫ **STOPPED**")
    
    with col2:
        st.markdown(f"📊 **Updates:** {status['update_count']}")
    
    with col3:
        if status['last_update']:
            time_diff = (datetime.now() - status['last_update']).seconds
            st.markdown(f"⏱️ **Last:** {time_diff}s ago")
        else:
            st.markdown("⏱️ **Last:** Never")
    
    with col4:
        if status['error_count'] > 0:
            st.markdown(f"⚠️ **Errors:** {status['error_count']}")
        else:
            st.markdown("✅ **Status:** OK")

def render_driver_cards(driver_stats, trends):
    """Render driver cards with real-time stats."""
    if not driver_stats:
        st.info("No driver data available yet")
        return
    
    # Create columns for each driver
    cols = st.columns(len(driver_stats))
    
    for i, (driver, stats) in enumerate(driver_stats.items()):
        trend = trends.get(driver, {})
        
        # Determine health color
        health = stats['health']
        if health > 70:
            health_color = "#4CAF50"
            health_emoji = "🟢"
        elif health > 30:
            health_color = "#FF9800"
            health_emoji = "🟡"
        else:
            health_color = "#f44336"
            health_emoji = "🔴"
        
        # Determine trend indicator
        trend_direction = trend.get('trend_direction', 'stable')
        if trend_direction == 'increasing':
            trend_emoji = "📈"
            trend_color = "#f44336"
        elif trend_direction == 'decreasing':
            trend_emoji = "📉"
            trend_color = "#4CAF50"
        else:
            trend_emoji = "➡️"
            trend_color = "#FF9800"
        
        with cols[i]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
                border-radius: 10px;
                padding: 1rem;
                border-left: 4px solid {health_color};
                margin: 0.5rem 0;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: #e10600; margin: 0;">{driver}</h3>
                    <span style="font-size: 1.2rem;">{health_emoji}</span>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin: 0.5rem 0;">
                    <span style="color: #888;">Lap {stats['lap']}</span>
                    <span style="color: #888;">Stint {stats['stint']}</span>
                </div>
                
                <div style="text-align: center; margin: 0.5rem 0;">
                    <span style="font-size: 1.2rem;">🏎️ {stats['compound']}</span>
                    <span style="color: #888; margin-left: 0.5rem;">(L{stats['tyre_life']})</span>
                </div>
                
                <div style="text-align: center; margin: 0.5rem 0;">
                    <span style="font-size: 2.5rem; font-weight: 700; color: {health_color};">
                        {health:.1f}%
                    </span>
                </div>
                
                <div style="display: flex; justify-content: space-around; margin: 0.5rem 0;">
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.8rem;">Last Lap</span>
                        <br>
                        <span style="font-size: 1.1rem; font-weight: 600;">{stats['last_lap']:.3f}s</span>
                    </div>
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.8rem;">Best Lap</span>
                        <br>
                        <span style="font-size: 1.1rem; font-weight: 600;">{stats['best_lap']:.3f}s</span>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-around; margin: 0.5rem 0;">
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.8rem;">Degradation</span>
                        <br>
                        <span style="font-size: 1.1rem; font-weight: 600; color: {'#f44336' if stats['degradation'] > 1 else '#FF9800' if stats['degradation'] > 0.5 else '#4CAF50'};">
                            +{stats['degradation']:.2f}s
                        </span>
                    </div>
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.8rem;">Stint Avg</span>
                        <br>
                        <span style="font-size: 1.1rem; font-weight: 600;">
                            {stats['stint_avg_degradation']:.2f}s
                        </span>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #333;">
                    <span style="color: #888; font-size: 0.9rem;">
                        {trend_emoji} Rate: {trend.get('degradation_rate', 0):.3f}s/lap
                    </span>
                    <span style="color: {trend_color}; font-size: 0.9rem;">
                        {trend.get('laps_remaining', '?')} laps est.
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

def create_live_chart(processed_data):
    """Create live degradation chart."""
    if processed_data is None or len(processed_data) == 0:
        return None
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Live Degradation', 'Tire Health', 
                       'Lap Times', 'Degradation Rate'),
        vertical_spacing=0.15,
        horizontal_spacing=0.15
    )
    
    colors = {'SOFT': '#e10600', 'MEDIUM': '#ffd700', 'HARD': '#c0c0c0', 
              'INTERMEDIATE': '#228b22', 'WET': '#4169e1'}
    
    for driver in processed_data['Driver'].unique():
        driver_data = processed_data[processed_data['Driver'] == driver]
        compound = driver_data['Compound'].iloc[-1]
        color = colors.get(compound, '#808080')
        
        # Degradation plot
        fig.add_trace(
            go.Scatter(
                x=driver_data['LapNumber'],
                y=driver_data['DegradationDelta'],
                mode='lines+markers',
                name=f'{driver}',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                hovertemplate='Lap %{x}<br>Delta: %{y:.3f}s<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Health plot
        fig.add_trace(
            go.Scatter(
                x=driver_data['LapNumber'],
                y=driver_data['HealthScore'],
                mode='lines+markers',
                name=f'{driver}',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                showlegend=False,
                hovertemplate='Lap %{x}<br>Health: %{y:.1f}%<extra></extra>'
            ),
            row=1, col=2
        )
        
        # Lap times plot
        fig.add_trace(
            go.Scatter(
                x=driver_data['LapNumber'],
                y=driver_data['LapTimeSeconds'],
                mode='lines+markers',
                name=f'{driver}',
                line=dict(color=color, width=2),
                marker=dict(size=6),
                showlegend=False,
                hovertemplate='Lap %{x}<br>Time: %{y:.3f}s<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Degradation rate (rolling average)
        if len(driver_data) >= 3:
            driver_data['DegRate'] = driver_data['DegradationDelta'].rolling(3).mean().diff()
            fig.add_trace(
                go.Scatter(
                    x=driver_data['LapNumber'],
                    y=driver_data['DegRate'],
                    mode='lines',
                    name=f'{driver}',
                    line=dict(color=color, width=2, dash='dot'),
                    showlegend=False,
                    hovertemplate='Lap %{x}<br>Rate: %{y:.3f}s/lap<extra></extra>'
                ),
                row=2, col=2
            )
    
    # Update layout
    fig.update_layout(
        height=700,
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
            'text': "Live Tire Degradation Monitoring",
            'y':0.98,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=20, color='#e10600')
        }
    )
    
    # Update axes
    fig.update_xaxes(title_text="Lap Number", gridcolor='#333333', row=1, col=1)
    fig.update_xaxes(title_text="Lap Number", gridcolor='#333333', row=1, col=2)
    fig.update_xaxes(title_text="Lap Number", gridcolor='#333333', row=2, col=1)
    fig.update_xaxes(title_text="Lap Number", gridcolor='#333333', row=2, col=2)
    
    fig.update_yaxes(title_text="Degradation (s)", gridcolor='#333333', row=1, col=1)
    fig.update_yaxes(title_text="Health (%)", gridcolor='#333333', row=1, col=2)
    fig.update_yaxes(title_text="Lap Time (s)", gridcolor='#333333', row=2, col=1)
    fig.update_yaxes(title_text="Rate (s/lap)", gridcolor='#333333', row=2, col=2)
    
    # Add horizontal line at y=0 for degradation plot
    fig.add_hline(y=0, line_dash="dash", line_color="#e10600", opacity=0.3, row=1, col=1)
    
    return fig

def render_live_table(processed_data):
    """Render live data table."""
    if processed_data is None or len(processed_data) == 0:
        st.info("No data available")
        return
    
    # Get latest lap for each driver
    latest_data = []
    for driver in processed_data['Driver'].unique():
        driver_data = processed_data[processed_data['Driver'] == driver]
        latest = driver_data.iloc[-1].to_dict()
        latest_data.append(latest)
    
    df = pd.DataFrame(latest_data)
    
    # Select and order columns
    display_cols = ['Driver', 'LapNumber', 'TyreLife', 'Compound', 'Stint',
                   'LapTimeSeconds', 'DegradationDelta', 'HealthScore']
    
    st.dataframe(
        df[display_cols].sort_values('Driver'),
        width="stretch",
        hide_index=True,
        column_config={
            "LapTimeSeconds": st.column_config.NumberColumn(format="%.3f s"),
            "DegradationDelta": st.column_config.NumberColumn(format="%.3f s"),
            "HealthScore": st.column_config.NumberColumn(format="%.1f %%")
        }
    )

def render_live_controls():
    """Render live monitoring controls."""
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
    
    with col1:
        start = st.button("▶️ Start", type="primary", width="stretch")
    
    with col2:
        pause = st.button("⏸️ Pause", width="stretch")
    
    with col3:
        resume = st.button("▶️ Resume", width="stretch")
    
    with col4:
        stop = st.button("⏹️ Stop", width="stretch")
    
    with col5:
        refresh = st.button("🔄 Refresh", width="stretch")
    
    return start, pause, resume, stop, refresh