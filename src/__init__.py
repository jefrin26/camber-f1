"""
Core modules for F1 tire degradation analysis.
"""

from .tire_model import (
    calculate_fuel_correction_vectorized,
    calculate_degradation_delta,
    calculate_health_score,
    add_health_scores,
    calculate_stint_statistics,
    create_degradation_chart,
    create_heatmap
)

from .data_fetcher import (
    fetch_race_data,
    get_available_races,
    check_data_quality,
    get_feature_availability
)

__all__ = [
    'calculate_fuel_correction_vectorized',
    'calculate_degradation_delta',
    'calculate_health_score',
    'add_health_scores',
    'calculate_stint_statistics',
    'create_degradation_chart',
    'create_heatmap',
    'fetch_race_data',
    'get_available_races',
    'check_data_quality',
    'get_feature_availability'
]