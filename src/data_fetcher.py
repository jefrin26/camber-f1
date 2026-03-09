import fastf1
import pandas as pd
import logging
import os

# Configure standard python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create cache directory if it doesn't exist
cache_dir = 'cache'
os.makedirs(cache_dir, exist_ok=True)

# Enable caching to avoid re-downloading data every time
# Creates a 'cache' folder in your current directory
fastf1.Cache.enable_cache(cache_dir) 

def get_race_data(year: int, round: int, driver: str):
    """
    Fetches lap times and tire compound data for a specific driver.
    
    Args:
        year (int): Season year (e.g., 2023)
        round (int): Race round number (e.g., 22 for Abu Dhabi)
        driver (str): Driver abbreviation (e.g., 'VER', 'HAM')
    
    Returns:
        pd.DataFrame: Cleaned dataframe with Lap, Time, Compound, and Stint info.
    """
    logger.info(f"Loading data for {year} Round {round} - Driver: {driver}...")
    
    try:
        # Load session
        # 'R' stands for Race. Use 'Q' for Qualifying, etc.
        session = fastf1.get_session(year, round, 'R')
        session.load()
        
        # Get laps for the specific driver
        # .pick_quicklaps() removes outliers (like pit laps or red flag laps)
        laps = session.laps.pick_drivers([driver]).pick_quicklaps()
        
        # Select relevant columns
        data = laps[['LapNumber', 'LapTime', 'Compound', 'Stint', 'TyreLife']].copy()
        
        # Convert LapTime to seconds for easier math later
        # Handle cases where LapTime might be NaT (Not a Time)
        data['LapTimeSeconds'] = data['LapTime'].apply(lambda x: x.total_seconds() if pd.notna(x) else None)
        
        # Drop rows where LapTimeSeconds is None
        data = data.dropna(subset=['LapTimeSeconds'])
        
        logger.info(f"Successfully loaded {len(data)} laps.")
        return data

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

if __name__ == "__main__":
    df = get_race_data(2026, 1, 'HAM')
    
    if df is not None:
        print("\n--- First 5 Laps Preview ---")
        print(df.head())
        print("\n--- Tire Compounds Used ---")
        print(df['Compound'].value_counts())
    else:
        print("Failed to retrieve data. Check your internet connection or cache.")