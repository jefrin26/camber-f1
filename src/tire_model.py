"""
Tire degradation model for Formula 1 data analysis.

This module implements physics calculations for tire performance modeling,
including fuel correction, stint grouping, and health score normalization.
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def calculate_fuel_correction(row: pd.Series, 
                             fuel_decay_per_lap: float = 2.5, 
                             time_penalty_per_kg: float = 0.035) -> float:
    """
    Calculate fuel correction for a single lap.
    
    Args:
        row: DataFrame row containing lap data
        fuel_decay_per_lap: Amount of fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
    
    Returns:
        float: Corrected lap time accounting for fuel load
    """
    # Get current lap in stint
    laps_completed = row.get('TyreLife', row.get('LapNumber', 1))
    
    # Need total stint length to calculate remaining fuel
    if 'StintLength' in row.index:
        total_stint_laps = row['StintLength']
    else:
        logger.debug("StintLength not available, returning raw time")
        return row['LapTimeSeconds']
    
    # Calculate remaining laps in stint
    remaining_laps = max(0, total_stint_laps - laps_completed)
    
    # Calculate fuel penalty based on remaining fuel
    fuel_penalty = remaining_laps * fuel_decay_per_lap * time_penalty_per_kg
    
    # Corrected time = raw time - fuel penalty (normalize to empty tank)
    corrected_time = row['LapTimeSeconds'] - fuel_penalty
    
    return corrected_time


def calculate_fuel_correction_vectorized(df: pd.DataFrame, 
                                        fuel_decay_per_lap: float = 2.5, 
                                        time_penalty_per_kg: float = 0.035) -> pd.Series:
    """
    Calculate fuel correction for an entire DataFrame efficiently.
    
    Args:
        df: DataFrame with lap data
        fuel_decay_per_lap: Amount of fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
    
    Returns:
        pd.Series: Series of corrected lap times
    """
    result_df = df.copy()
    
    # Calculate stint lengths if not present
    if 'StintLength' not in result_df.columns:
        stint_lengths = result_df.groupby('Stint')['TyreLife'].transform('max')
        result_df['StintLength'] = stint_lengths
    
    # Get laps completed
    laps_completed = result_df.get('TyreLife', result_df.get('LapNumber'))
    
    # Calculate remaining laps
    remaining_laps = result_df['StintLength'] - laps_completed
    remaining_laps = remaining_laps.clip(lower=0)
    
    # Calculate fuel penalty
    fuel_penalty = remaining_laps * fuel_decay_per_lap * time_penalty_per_kg
    
    # Corrected times
    corrected_times = result_df['LapTimeSeconds'] - fuel_penalty
    
    return corrected_times


def calculate_degradation_delta(df: pd.DataFrame, 
                               fuel_decay_per_lap: float = 2.5, 
                               time_penalty_per_kg: float = 0.035,
                               benchmark_method: str = 'fastest') -> pd.DataFrame:
    """
    Calculate degradation delta for each lap in the dataset.
    
    Args:
        df: DataFrame with lap data
        fuel_decay_per_lap: Fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
        benchmark_method: Method to calculate benchmark ('fastest', 'median', 'second_lap')
    
    Returns:
        pd.DataFrame: Original DataFrame with added columns
    """
    # Make a copy
    result_df = df.copy()
    
    # Calculate stint lengths
    if 'StintLength' not in result_df.columns:
        stint_lengths = result_df.groupby('Stint')['TyreLife'].transform('max')
        result_df['StintLength'] = stint_lengths
    
    # Calculate corrected times
    logger.info("Calculating fuel-corrected lap times...")
    result_df['CorrectedTime'] = calculate_fuel_correction_vectorized(
        result_df, fuel_decay_per_lap, time_penalty_per_kg
    )
    
    # Initialize columns
    result_df['DegradationDelta'] = 0.0
    result_df['FreshTireBenchmark'] = 0.0
    
    # Calculate per-stint benchmarks
    logger.info("Calculating degradation per stint...")
    
    for stint_num in result_df['Stint'].unique():
        stint_mask = result_df['Stint'] == stint_num
        stint_data = result_df[stint_mask]
        
        # Calculate benchmark based on method
        if benchmark_method == 'fastest':
            benchmark_time = stint_data['CorrectedTime'].min()
        elif benchmark_method == 'median':
            benchmark_time = stint_data['CorrectedTime'].median()
        elif benchmark_method == 'second_lap':
            # Use the second lap of the stint (after tires warm up)
            if len(stint_data) >= 2:
                second_lap = stint_data[stint_data['TyreLife'] == 2]
                if not second_lap.empty:
                    benchmark_time = second_lap['CorrectedTime'].iloc[0]
                else:
                    benchmark_time = stint_data['CorrectedTime'].min()
            else:
                benchmark_time = stint_data['CorrectedTime'].min()
        else:
            benchmark_time = stint_data['CorrectedTime'].min()
        
        # Assign benchmark
        result_df.loc[stint_mask, 'FreshTireBenchmark'] = benchmark_time
        
        # Calculate degradation delta
        result_df.loc[stint_mask, 'DegradationDelta'] = (
            result_df.loc[stint_mask, 'CorrectedTime'] - benchmark_time
        )
    
    return result_df


def calculate_health_score(degradation_delta: float, 
                          max_degradation: float = 2.5) -> float:
    """
    Convert degradation delta into a percentage health score.
    
    Args:
        degradation_delta: Time difference from fresh tire benchmark (seconds)
        max_degradation: Threshold where health drops to 0% (seconds)
    
    Returns:
        float: Health score as percentage (0-100%)
    """
    # Normalize degradation to 0-1 scale
    normalized = np.clip(degradation_delta / max_degradation, 0, 1)
    health_score = (1 - normalized) * 100
    
    return float(np.maximum(health_score, 0))


def add_health_scores(df: pd.DataFrame, 
                     max_degradation: float = 2.5) -> pd.DataFrame:
    """
    Add health scores to the DataFrame.
    
    Args:
        df: DataFrame with 'DegradationDelta' column
        max_degradation: Threshold where health drops to 0% (seconds)
    
    Returns:
        pd.DataFrame: Original DataFrame with added 'HealthScore' column
    """
    result_df = df.copy()
    
    if 'DegradationDelta' not in result_df.columns:
        raise ValueError("DataFrame must contain 'DegradationDelta' column")
    
    result_df['HealthScore'] = result_df['DegradationDelta'].apply(
        lambda x: calculate_health_score(x, max_degradation)
    )
    
    return result_df


def calculate_stint_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate per-stint statistics.
    
    Args:
        df: DataFrame with degradation analysis
    
    Returns:
        pd.DataFrame: Stint-level statistics
    """
    stats = []
    
    for stint in df['Stint'].unique():
        stint_data = df[df['Stint'] == stint]
        
        # Get compound
        compound = stint_data['Compound'].iloc[0] if len(stint_data) > 0 else 'Unknown'
        
        # Calculate metrics
        stint_stats = {
            'Stint': stint,
            'Compound': compound,
            'Laps': len(stint_data),
            'Avg_LapTime': stint_data['LapTimeSeconds'].mean(),
            'Best_LapTime': stint_data['LapTimeSeconds'].min(),
            'Avg_CorrectedTime': stint_data['CorrectedTime'].mean(),
            'Best_CorrectedTime': stint_data['CorrectedTime'].min(),
            'Avg_Degradation': stint_data['DegradationDelta'].mean(),
            'Max_Degradation': stint_data['DegradationDelta'].max(),
            'Avg_Health': stint_data['HealthScore'].mean(),
            'Min_Health': stint_data['HealthScore'].min(),
        }
        stats.append(stint_stats)
    
    return pd.DataFrame(stats)


if __name__ == "__main__":
    # Example usage with sample data
    sample_data = pd.DataFrame({
        'LapTimeSeconds': [95.0, 94.8, 95.2, 95.5, 94.9, 95.3],
        'TyreLife': [1, 2, 3, 1, 2, 3],
        'Stint': [1, 1, 1, 2, 2, 2],
        'Compound': ['SOFT', 'SOFT', 'SOFT', 'HARD', 'HARD', 'HARD']
    })
    
    result = calculate_degradation_delta(sample_data)
    result = add_health_scores(result)
    stats = calculate_stint_statistics(result)
    
    print("Sample Data Analysis:")
    print(result[['TyreLife', 'LapTimeSeconds', 'CorrectedTime', 
                 'DegradationDelta', 'HealthScore']])
    print("\nStint Statistics:")
    print(stats)