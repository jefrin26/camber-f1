"""
Tests for the tire model functions.
"""

import pandas as pd
import numpy as np
from src.tire_model import (
    calculate_fuel_correction,
    calculate_fuel_correction_vectorized,
    calculate_degradation_delta,
    calculate_health_score,
    add_health_scores
)


def test_fuel_correction():
    """Test the fuel correction calculation."""
    print("Testing fuel correction...")
    
    # Create a mock row with lap data
    mock_row = pd.Series({
        'LapTimeSeconds': 90.0,
        'LapNumber': 5,
        'TyreLife': 5,
        'Stint': 1
    })
    
    corrected_time = calculate_fuel_correction(mock_row)
    print(f"Raw time: {mock_row['LapTimeSeconds']:.3f}s")
    print(f"Corrected time: {corrected_time:.3f}s")
    print(f"Difference: {corrected_time - mock_row['LapTimeSeconds']:.3f}s")
    
    # Verify that corrected time is greater than raw time due to fuel penalty
    assert corrected_time > mock_row['LapTimeSeconds'], "Corrected time should be higher due to fuel penalty"
    print("✓ Fuel correction test passed\n")


def test_degradation_calculation():
    """Test the degradation delta calculation."""
    print("Testing degradation calculation...")
    
    # Create mock data for a single stint
    mock_data = pd.DataFrame({
        'LapTimeSeconds': [90.0, 90.2, 90.5, 90.8, 91.2],
        'LapNumber': [1, 2, 3, 4, 5],
        'TyreLife': [1, 2, 3, 4, 5],  # Laps since tire change
        'Stint': [1, 1, 1, 1, 1],
        'Compound': ['SOFT', 'SOFT', 'SOFT', 'SOFT', 'SOFT']
    })
    
    result_df = calculate_degradation_delta(mock_data)
    
    print("Original DataFrame:")
    print(result_df[['LapTimeSeconds', 'CorrectedTime', 'DegradationDelta']])
    
    # Verify that degradation increases over laps in a stint
    assert all(result_df['DegradationDelta'].diff().dropna() >= 0), "Degradation should increase or stay same over laps"
    print("✓ Degradation calculation test passed\n")


def test_health_score():
    """Test the health score calculation."""
    print("Testing health score calculation...")
    
    # Test various degradation values
    test_values = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    expected_scores = [100.0, 80.0, 60.0, 40.0, 20.0, 0.0, 0.0]  # Based on max_degradation=2.5
    
    for val, expected in zip(test_values, expected_scores):
        score = calculate_health_score(val)
        print(f"Degradation: {val}s -> Health: {score:.1f}% (expected: {expected}%)")
        assert abs(score - expected) < 0.1, f"Expected {expected}, got {score}"
    
    print("✓ Health score test passed\n")


def test_multi_stint_scenario():
    """Test degradation calculation across multiple stints."""
    print("Testing multi-stint scenario...")
    
    # Create mock data with two stints
    mock_data = pd.DataFrame({
        'LapTimeSeconds': [90.0, 90.2, 90.5, 89.8, 90.1, 90.4],  # Second stint starts with lower times
        'LapNumber': [1, 2, 3, 4, 5, 6],
        'TyreLife': [1, 2, 3, 1, 2, 3],  # Resets at new stint
        'Stint': [1, 1, 1, 2, 2, 2],  # Two stints
        'Compound': ['SOFT', 'SOFT', 'SOFT', 'HARD', 'HARD', 'HARD']
    })
    
    result_df = calculate_degradation_delta(mock_data)
    
    print("Multi-stint DataFrame:")
    print(result_df[['LapTimeSeconds', 'Stint', 'CorrectedTime', 'FreshTireBenchmark', 'DegradationDelta']])
    
    # Verify that the second stint has a new benchmark (should be around the lowest time in stint 2)
    stint1_benchmark = result_df[result_df['Stint'] == 1]['FreshTireBenchmark'].iloc[0]
    stint2_benchmark = result_df[result_df['Stint'] == 2]['FreshTireBenchmark'].iloc[3]  # First row of stint 2
    
    print(f"Stint 1 benchmark: {stint1_benchmark:.3f}s")
    print(f"Stint 2 benchmark: {stint2_benchmark:.3f}s")
    
    # The benchmark for stint 2 should be based on the minimum corrected time in that stint
    expected_stint2_benchmark = result_df[result_df['Stint'] == 2]['CorrectedTime'].min()
    assert abs(stint2_benchmark - expected_stint2_benchmark) < 0.001, "Stint 2 benchmark should match min corrected time in that stint"
    
    print("✓ Multi-stint scenario test passed\n")


def test_health_score_addition():
    """Test adding health scores to a DataFrame."""
    print("Testing health score addition...")
    
    # Create mock data
    mock_data = pd.DataFrame({
        'LapTimeSeconds': [90.0, 90.5, 91.0, 91.5, 92.0],
        'LapNumber': [1, 2, 3, 4, 5],
        'TyreLife': [1, 2, 3, 4, 5],
        'Stint': [1, 1, 1, 1, 1],
        'Compound': ['MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM'],
        'DegradationDelta': [0.0, 0.2, 0.4, 0.6, 0.8]
    })
    
    result_df = add_health_scores(mock_data)
    
    print("DataFrame with health scores:")
    print(result_df[['LapTimeSeconds', 'DegradationDelta', 'HealthScore']])
    
    # Verify health scores are calculated correctly
    expected_scores = [100.0, 92.0, 84.0, 76.0, 68.0]  # Based on max_degradation=2.5
    for i, expected in enumerate(expected_scores):
        actual = result_df.iloc[i]['HealthScore']
        assert abs(actual - expected) < 0.1, f"Expected {expected}, got {actual}"
    
    print("✓ Health score addition test passed\n")


if __name__ == "__main__":
    print("Running tire model tests...\n")
    
    test_fuel_correction()
    test_degradation_calculation()
    test_health_score()
    test_multi_stint_scenario()
    test_health_score_addition()
    
    print("All tests passed! ✓")