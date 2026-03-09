"""
Tire degradation model for Formula 1 data analysis.

This module implements physics calculations for tire performance modeling,
including fuel correction, stint grouping, and health score normalization.
"""

import pandas as pd
import numpy as np


def calculate_fuel_correction(row, fuel_decay_per_lap=2.5, time_penalty_per_kg=0.035):
    """
    Calculate fuel correction for a single lap.
    
    Args:
        row: DataFrame row containing lap data
        fuel_decay_per_lap: Amount of fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
    
    Returns:
        float: Corrected lap time accounting for fuel load
    """
    # Calculate laps in current stint (using TyreLife as proxy for laps in stint)
    # Assuming TyreLife represents how many laps the tire has done
    laps_in_stint = row['TyreLife'] if 'TyreLife' in row.index else row.get('LapNumber', 1)
    
    # Calculate fuel penalty based on position in stint
    # At the beginning of a stint, the car is heaviest (more laps to go)
    # So we need to add back the fuel penalty for all laps in the stint
    total_fuel_penalty = laps_in_stint * fuel_decay_per_lap * time_penalty_per_kg
    
    # Corrected time = raw time + fuel penalty (to normalize for fuel load)
    corrected_time = row['LapTimeSeconds'] + total_fuel_penalty
    
    return corrected_time


def calculate_fuel_correction_vectorized(df, fuel_decay_per_lap=2.5, time_penalty_per_kg=0.035):
    """
    Calculate fuel correction for an entire DataFrame efficiently.
    
    Args:
        df: DataFrame with lap data
        fuel_decay_per_lap: Amount of fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
    
    Returns:
        pd.Series: Series of corrected lap times
    """
    # Calculate laps in current stint (using TyreLife as proxy for laps in stint)
    # At the beginning of a stint, the car is heaviest (more laps to go)
    laps_in_stint = df['TyreLife'] if 'TyreLife' in df.columns else df['LapNumber']
    
    # Calculate fuel penalty based on position in stint
    total_fuel_penalty = laps_in_stint * fuel_decay_per_lap * time_penalty_per_kg
    
    # Corrected time = raw time + fuel penalty (to normalize for fuel load)
    corrected_times = df['LapTimeSeconds'] + total_fuel_penalty
    
    return corrected_times


def calculate_degradation_delta(df, fuel_decay_per_lap=2.5, time_penalty_per_kg=0.035):
    """
    Calculate degradation delta for each lap in the dataset.
    
    Args:
        df: DataFrame with lap data including 'LapTimeSeconds', 'Stint', 'Compound'
        fuel_decay_per_lap: Amount of fuel burned per lap (kg)
        time_penalty_per_kg: Time penalty per kg of fuel (seconds)
    
    Returns:
        pd.DataFrame: Original DataFrame with added columns for corrected times and degradation
    """
    # Make a copy to avoid modifying the original
    result_df = df.copy()
    
    # Calculate corrected times accounting for fuel
    result_df['CorrectedTime'] = calculate_fuel_correction_vectorized(
        result_df, fuel_decay_per_lap, time_penalty_per_kg
    )
    
    # Group by stint to calculate baseline for each stint
    result_df['DegradationDelta'] = 0.0
    result_df['FreshTireBenchmark'] = 0.0
    
    for stint_num in result_df['Stint'].unique():
        stint_mask = result_df['Stint'] == stint_num
        
        # Get the minimum corrected time for this stint as the benchmark
        stint_data = result_df[stint_mask]
        benchmark_time = stint_data['CorrectedTime'].min()
        
        # Assign benchmark to all laps in this stint
        result_df.loc[stint_mask, 'FreshTireBenchmark'] = benchmark_time
        
        # Calculate degradation delta for this stint
        result_df.loc[stint_mask, 'DegradationDelta'] = (
            result_df.loc[stint_mask, 'CorrectedTime'] - benchmark_time
        )
    
    return result_df


def calculate_health_score(degradation_delta, max_degradation=2.5):
    """
    Convert degradation delta into a percentage health score.
    
    Args:
        degradation_delta: Time difference from fresh tire benchmark (seconds)
        max_degradation: Threshold where health drops to 0% (seconds)
    
    Returns:
        float: Health score as percentage (0-100%)
    """
    # Normalize degradation to 0-1 scale, then convert to percentage
    normalized = np.clip(degradation_delta / max_degradation, 0, 1)
    health_score = (1 - normalized) * 100
    
    # Ensure health score doesn't go below 0
    return np.maximum(health_score, 0)


def add_health_scores(df, max_degradation=2.5):
    """
    Add health scores to the DataFrame.
    
    Args:
        df: DataFrame with 'DegradationDelta' column
        max_degradation: Threshold where health drops to 0% (seconds)
    
    Returns:
        pd.DataFrame: Original DataFrame with added 'HealthScore' column
    """
    result_df = df.copy()
    result_df['HealthScore'] = calculate_health_score(
        result_df['DegradationDelta'], max_degradation
    )
    return result_df


if __name__ == "__main__":
    # Example usage
    print("Tire model functions defined.")
    print("- calculate_fuel_correction: Adjusts lap times for fuel load")
    print("- calculate_degradation_delta: Calculates degradation relative to stint benchmark")
    print("- calculate_health_score: Converts degradation to percentage health")