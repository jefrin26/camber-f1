#!/usr/bin/env python3
"""
Main entry point for Camber F1 tire degradation analysis.
Run this script from the project root directory.
"""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.analysis_pipeline import F1TireAnalysisPipeline, quick_analyze

def main():
    """Main function to run the analysis."""
    print("=" * 60)
    print("CAMBER F1 - TIRE DEGRADATION ANALYSIS")
    print("=" * 60)
    
    # Configuration
    YEAR = 2023
    ROUND = 22  # Abu Dhabi
    DRIVER = 'VER'
    
    # Initialize pipeline
    pipeline = F1TireAnalysisPipeline()
    
    # Run analysis
    df = pipeline.run_driver_analysis(
        year=YEAR,
        round_num=ROUND,
        driver=DRIVER,
        session_type='R',
        fuel_decay_per_lap=2.5,
        time_penalty_per_kg=0.035,
        max_degradation=2.5,
        benchmark_method='fastest'
    )
    
    if df is not None:
        print(f"\n✅ Analysis complete for {DRIVER} at {YEAR} Round {ROUND}")
        print(f"📊 Total laps analyzed: {len(df)}")
        print(f"📈 Results saved to: {pipeline.output_dir}")
        
        # Export results
        pipeline.export_results('csv')
        
        # Show summary
        print("\n📊 Stint Summary:")
        stints = pipeline.results.get(f"{DRIVER}_{YEAR}_R{ROUND}", {}).get('stints')
        if stints is not None:
            print(stints.to_string())
    else:
        print("❌ Analysis failed. Check logs for details.")

if __name__ == "__main__":
    main()