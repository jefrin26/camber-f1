"""
Integration test for the tire model.

This script fetches real F1 data and applies the tire degradation model.
"""

import pandas as pd
from src.data_fetcher import get_race_data
from src.tire_model import calculate_degradation_delta, add_health_scores


def run_integration_test():
    """
    Run the complete integration test:
    1. Fetch race data
    2. Apply tire model
    3. Display results
    """
    print("🔍 Starting tire model integration test...")
    
    # Fetch real data - using a past race since 2026 data isn't available yet
    print("📊 Fetching race data...")
    df = get_race_data(2023, 22, 'VER')  # 2023 Abu Dhabi GP, Verstappen
    
    if df is None or df.empty:
        print("❌ Failed to retrieve data. Exiting.")
        return
    
    print(f"✅ Retrieved {len(df)} laps of data")
    print(f"📋 Columns available: {list(df.columns)}")
    
    # Apply the tire model
    print("\n⚙️ Applying tire degradation model...")
    df_with_degradation = calculate_degradation_delta(df)
    
    # Add health scores
    df_final = add_health_scores(df_with_degradation)
    
    print("✅ Tire model applied successfully!")
    
    # Display results
    print("\n📈 Sample results:")
    print(df_final[
        ['LapNumber', 'Compound', 'LapTimeSeconds', 'CorrectedTime', 
         'DegradationDelta', 'HealthScore']
    ].head(10))
    
    # Perform sanity checks
    print("\n✅ Performing sanity checks...")
    
    # Check 1: The Upward Trend - degradation should generally increase within a stint
    for stint_num in df_final['Stint'].unique():
        stint_data = df_final[df_final['Stint'] == stint_num].sort_values('LapNumber')
        if len(stint_data) > 1:
            degradation_trend = stint_data['DegradationDelta'].diff().dropna()
            positive_changes = (degradation_trend >= 0).sum()
            total_changes = len(degradation_trend)
            
            print(f"   Stint {int(stint_num)}: {positive_changes}/{total_changes} laps show increasing degradation")
    
    # Check 2: The Reset - degradation should be near zero at the start of new stints
    print("\n🔄 Checking stint resets...")
    for stint_num in sorted(df_final['Stint'].unique()):
        stint_start_data = df_final[
            (df_final['Stint'] == stint_num) & 
            (df_final['TyreLife'] == df_final[df_final['Stint'] == stint_num]['TyreLife'].min())
        ]
        avg_start_degradation = stint_start_data['DegradationDelta'].mean()
        print(f"   Stint {int(stint_num)} start avg degradation: {avg_start_degradation:.3f}s")
    
    # Check 3: Compound Differences - compare average degradation rates
    print("\n🧪 Comparing compound degradation...")
    compound_degradation_rates = df_final.groupby('Compound')['DegradationDelta'].mean()
    print("Average degradation by compound:")
    for compound, avg_deg in compound_degradation_rates.items():
        if pd.notna(compound):  # Skip NaN compounds
            print(f"   {compound}: {avg_deg:.3f}s")
    
    print("\n🏁 Integration test completed successfully!")


if __name__ == "__main__":
    run_integration_test()