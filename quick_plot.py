import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load data
df = pd.read_csv('outputs/VER_2023_R22_laps.csv')

# Create figure
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=('Lap Times', 'Degradation', 'Tire Health', 'Compound Analysis')
)

# Color mapping for compounds
colors = {'MEDIUM': 'orange', 'HARD': 'blue'}

# 1. Lap Times
for stint in df['Stint'].unique():
    stint_data = df[df['Stint'] == stint]
    color = colors[stint_data['Compound'].iloc[0]]
    fig.add_trace(
        go.Scatter(x=stint_data['TyreLife'], y=stint_data['LapTimeSeconds'],
                  mode='lines+markers', name=f'Stint {stint}',
                  line=dict(color=color, width=2)),
        row=1, col=1
    )

# 2. Degradation
for stint in df['Stint'].unique():
    stint_data = df[df['Stint'] == stint]
    color = colors[stint_data['Compound'].iloc[0]]
    fig.add_trace(
        go.Scatter(x=stint_data['TyreLife'], y=stint_data['DegradationDelta'],
                  mode='lines+markers', name=f'Stint {stint}',
                  line=dict(color=color, width=2), showlegend=False),
        row=1, col=2
    )

# 3. Health Score
for stint in df['Stint'].unique():
    stint_data = df[df['Stint'] == stint]
    color = colors[stint_data['Compound'].iloc[0]]
    fig.add_trace(
        go.Scatter(x=stint_data['TyreLife'], y=stint_data['HealthScore'],
                  mode='lines+markers', name=f'Stint {stint}',
                  line=dict(color=color, width=2), showlegend=False),
        row=2, col=1
    )

# 4. Compound comparison (box plots)
for compound in df['Compound'].unique():
    compound_data = df[df['Compound'] == compound]
    fig.add_trace(
        go.Box(y=compound_data['LapTimeSeconds'], name=compound,
               marker_color=colors[compound]),
        row=2, col=2
    )

# Update layout
fig.update_layout(height=800, title_text="Verstappen - 2023 Abu Dhabi GP Tire Analysis")
fig.update_xaxes(title_text="Tyre Life (Laps)", row=1, col=1)
fig.update_xaxes(title_text="Tyre Life (Laps)", row=1, col=2)
fig.update_xaxes(title_text="Tyre Life (Laps)", row=2, col=1)
fig.update_xaxes(title_text="Compound", row=2, col=2)

fig.show()