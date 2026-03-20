"""
Tire degradation model for Formula 1 data analysis.
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

#===============================================================================
# CORE CALCULATION FUNCTIONS
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
            if stint_data.empty:
                logger.warning(f"Empty stint data encountered for stint {stint_num}")
                continue
            benchmark_time = stint_data['CorrectedTime'].min()
        elif benchmark_method == 'second_lap' and len(stint_data) >= 2:
            second_lap = stint_data[stint_data['TyreLife'] == 2]
            benchmark_time = second_lap['CorrectedTime'].iloc[0] if not second_lap.empty else stint_data['CorrectedTime'].min()
        else:
            if stint_data.empty:
                logger.warning(f"Empty stint data encountered for stint {stint_num}")
                continue
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
    
    colors = {'SOFT': '#e10600', 'MEDIUM': '#ffd700', 'HARD': '#c0c0c0', 
              'INTERMEDIATE': '#228b22', 'WET': '#4169e1'}
    
    # 1. Lap Times
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        if stint_data.empty:
            continue
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
        if stint_data.empty:
            continue
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
        if stint_data.empty:
            continue
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