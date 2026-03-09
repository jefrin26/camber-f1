"""
Camber F1 - Tire Degradation Analysis Package
"""

from .data_fetcher import get_race_data
from .tire_model import (
    calculate_fuel_correction,
    calculate_fuel_correction_vectorized,
    calculate_degradation_delta,
    calculate_health_score,
    add_health_scores
)

__version__ = '0.1.0'