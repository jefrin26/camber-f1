"""
Complete analysis pipeline integrating data_fetcher and tire_model.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Import local modules
from . import data_fetcher
from . import tire_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'outputs'


class F1TireAnalysisPipeline:
    """Main pipeline for F1 tire degradation analysis."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the analysis pipeline.
        
        Args:
            output_dir: Directory to save outputs (default: PROJECT_ROOT/outputs)
        """
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
        
    def run_driver_analysis(self, 
                           year: int, 
                           round_num: int, 
                           driver: str,
                           session_type: str = 'R',
                           fuel_decay_per_lap: float = 2.5,
                           time_penalty_per_kg: float = 0.035,
                           max_degradation: float = 2.5,
                           benchmark_method: str = 'fastest') -> Optional[pd.DataFrame]:
        """
        Run complete analysis for a single driver.
        
        Args:
            year: Season year
            round_num: Race round number
            driver: Driver abbreviation
            session_type: Session type ('R' for Race, 'Q' for Qualifying)
            fuel_decay_per_lap: Fuel burned per lap (kg)
            time_penalty_per_kg: Time penalty per kg of fuel
            max_degradation: Threshold for 0% health
            benchmark_method: Method for stint benchmark
        
        Returns:
            DataFrame with complete analysis or None if failed
        """
        logger.info(f"=== Starting analysis for {driver} - {year} Round {round_num} ===")
        
        # Step 1: Fetch data
        df = data_fetcher.fetch_race_data(year, round_num, driver, session_type)
        
        if df is None or len(df) == 0:
            logger.error(f"No data retrieved for {driver}")
            return None
        
        logger.info(f"✅ Retrieved {len(df)} laps for {driver}")
        
        # Step 2: Calculate degradation
        df_with_degradation = tire_model.calculate_degradation_delta(
            df,
            fuel_decay_per_lap=fuel_decay_per_lap,
            time_penalty_per_kg=time_penalty_per_kg,
            benchmark_method=benchmark_method
        )
        
        # Step 3: Add health scores
        final_df = tire_model.add_health_scores(
            df_with_degradation,
            max_degradation=max_degradation
        )
        
        # Step 4: Calculate stint statistics
        stint_stats = tire_model.calculate_stint_statistics(final_df)
        
        # Store results
        result_key = f"{driver}_{year}_R{round_num}"
        self.results[result_key] = {
            'laps': final_df,
            'stints': stint_stats,
            'metadata': {
                'year': year,
                'round': round_num,
                'driver': driver,
                'session': session_type,
                'params': {
                    'fuel_decay_per_lap': fuel_decay_per_lap,
                    'time_penalty_per_kg': time_penalty_per_kg,
                    'max_degradation': max_degradation,
                    'benchmark_method': benchmark_method
                }
            }
        }
        
        logger.info(f"✅ Analysis complete for {driver}")
        
        return final_df
    
    def run_multi_driver_analysis(self,
                                 year: int,
                                 round_num: int,
                                 drivers: list,
                                 session_type: str = 'R',
                                 **kwargs) -> Dict[str, pd.DataFrame]:
        """
        Run analysis for multiple drivers.
        
        Args:
            year: Season year
            round_num: Race round number
            drivers: List of driver abbreviations
            session_type: Session type
            **kwargs: Additional parameters for run_driver_analysis
        
        Returns:
            Dictionary mapping driver to their results DataFrame
        """
        logger.info(f"=== Running multi-driver analysis for {len(drivers)} drivers ===")
        
        results = {}
        for driver in drivers:
            df = self.run_driver_analysis(
                year=year,
                round_num=round_num,
                driver=driver,
                session_type=session_type,
                **kwargs
            )
            if df is not None:
                results[driver] = df
        
        # Create comparison summary
        comparison = self._create_comparison_summary()
        
        if comparison is not None:
            self.results['comparison'] = comparison
        
        logger.info(f"✅ Multi-driver analysis complete. {len(results)} drivers processed.")
        
        return results
    
    def _create_comparison_summary(self) -> Optional[pd.DataFrame]:
        """Create summary comparing multiple drivers."""
        comparison_data = []
        
        for key, result in self.results.items():
            if key == 'comparison':
                continue
                
            if 'metadata' in result and 'stints' in result:
                meta = result['metadata']
                stints = result['stints']
                
                summary = {
                    'Driver': meta['driver'],
                    'Year': meta['year'],
                    'Round': meta['round'],
                    'Session': meta['session'],
                    'Total_Laps': len(result['laps']),
                    'Number_of_Stints': stints['Stint'].nunique(),
                    'Compounds': ', '.join(stints['Compound'].unique()),
                    'Avg_Health': result['laps']['HealthScore'].mean(),
                    'Min_Health': result['laps']['HealthScore'].min(),
                    'Avg_Degradation': result['laps']['DegradationDelta'].mean(),
                    'Max_Degradation': result['laps']['DegradationDelta'].max(),
                    'Best_Lap': result['laps']['LapTimeSeconds'].min(),
                }
                comparison_data.append(summary)
        
        if comparison_data:
            return pd.DataFrame(comparison_data)
        return None
    
    def export_results(self, format: str = 'csv'):
        """
        Export all results to files.
        
        Args:
            format: Export format ('csv' or 'parquet')
        """
        for key, result in self.results.items():
            if key == 'comparison':
                # Export comparison
                filepath = self.output_dir / f"comparison_{pd.Timestamp.now().strftime('%Y%m%d')}.{format}"
                if format == 'csv':
                    result.to_csv(filepath, index=False)
                else:
                    result.to_parquet(filepath)
                logger.info(f"✅ Exported comparison to {filepath}")
                
            elif 'laps' in result and 'stints' in result:
                # Export lap data
                lap_file = self.output_dir / f"{key}_laps.{format}"
                stint_file = self.output_dir / f"{key}_stints.{format}"
                
                if format == 'csv':
                    result['laps'].to_csv(lap_file, index=False)
                    result['stints'].to_csv(stint_file, index=False)
                else:
                    result['laps'].to_parquet(lap_file)
                    result['stints'].to_parquet(stint_file)
                
                logger.info(f"✅ Exported lap data to {lap_file}")
                logger.info(f"✅ Exported stint data to {stint_file}")
    
    def get_summary(self) -> pd.DataFrame:
        """Get a summary of all analyses performed."""
        if 'comparison' in self.results:
            return self.results['comparison']
        return self._create_comparison_summary() or pd.DataFrame()


# Convenience function for quick analysis
def quick_analyze(year: int, round_num: int, driver: str, **kwargs):
    """
    Quick one-line analysis function.
    
    Args:
        year: Season year
        round_num: Race round number
        driver: Driver abbreviation
        **kwargs: Additional parameters
    
    Returns:
        Tuple of (lap_data, stint_stats)
    """
    pipeline = F1TireAnalysisPipeline()
    df = pipeline.run_driver_analysis(year, round_num, driver, **kwargs)
    
    if df is not None:
        stint_stats = tire_model.calculate_stint_statistics(df)
        return df, stint_stats
    return None, None


if __name__ == "__main__":
    # Example usage
    print("=" * 60)
    print("CAMBER F1 - TIRE DEGRADATION ANALYSIS PIPELINE")
    print("=" * 60)
    
    # Initialize pipeline
    pipeline = F1TireAnalysisPipeline()
    
    # Analyze single driver
    df = pipeline.run_driver_analysis(
        year=2023,
        round_num=22,  # Abu Dhabi
        driver='VER',
        session_type='R',
        fuel_decay_per_lap=2.5,
        time_penalty_per_kg=0.035,
        max_degradation=2.5
    )
    
    if df is not None:
        print("\n📊 First 5 laps of analysis:")
        print(df[['LapNumber', 'TyreLife', 'Compound', 'LapTimeSeconds', 
                 'CorrectedTime', 'DegradationDelta', 'HealthScore']].head())
        
        # Analyze multiple drivers
        print("\n" + "=" * 60)
        drivers = ['VER', 'HAM', 'PER', 'LEC']
        pipeline.run_multi_driver_analysis(2023, 22, drivers)
        
        # Show comparison
        print("\n📈 Driver Comparison:")
        print(pipeline.get_summary().to_string())
        
        # Export results
        pipeline.export_results('csv')
        
        print(f"\n✅ All results saved to {pipeline.output_dir}")