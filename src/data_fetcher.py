"""
F1 data fetcher using FastF1 library.
"""

import fastf1
import pandas as pd
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the project root directory (where cache folder is)
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / 'cache'

# Enable FastF1 caching
fastf1.Cache.enable_cache(str(CACHE_DIR))

def get_race_data(year: int, round_num: int, driver: str, session_type: str = 'R'):
    """
    Fetches lap times and tire compound data for a specific driver.
    
    Args:
        year (int): Season year (e.g., 2023)
        round_num (int): Race round number (e.g., 22 for Abu Dhabi)
        driver (str): Driver abbreviation (e.g., 'VER', 'HAM')
        session_type (str): Session type ('R' for Race, 'Q' for Qualifying, etc.)
    
    Returns:
        pd.DataFrame: Cleaned dataframe with Lap, Time, Compound, and Stint info.
    """
    logger.info(f"Loading data for {year} Round {round_num} ({session_type}) - Driver: {driver}...")
    
    try:
        # Load session
        session = fastf1.get_session(year, round_num, session_type)
        session.load()
        
        # Get laps for the specific driver
        laps = session.laps.pick_drivers([driver])
        
        if len(laps) == 0:
            logger.warning(f"No laps found for {driver}")
            return None
        
        # Select relevant columns
        data = laps[['LapNumber', 'LapTime', 'Compound', 'Stint', 'TyreLife']].copy()
        
        # Convert LapTime to seconds
        data['LapTimeSeconds'] = data['LapTime'].apply(
            lambda x: x.total_seconds() if pd.notna(x) else None
        )
        
        # Drop rows with missing lap times
        data = data.dropna(subset=['LapTimeSeconds'])
        
        # Add metadata
        data['Year'] = year
        data['Round'] = round_num
        data['Driver'] = driver
        data['Session'] = session_type
        
        # Reset index
        data = data.reset_index(drop=True)
        
        logger.info(f"Successfully loaded {len(data)} laps for {driver}")
        return data

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

def get_multiple_drivers_data(year: int, round_num: int, drivers: list, session_type: str = 'R'):
    """
    Fetch data for multiple drivers in the same race.
    
    Args:
        year: Season year
        round_num: Race round number
        drivers: List of driver abbreviations
        session_type: Session type
    
    Returns:
        pd.DataFrame: Combined data for all drivers
    """
    all_data = []
    
    for driver in drivers:
        df = get_race_data(year, round_num, driver, session_type)
        if df is not None:
            all_data.append(df)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

def get_available_races(year: int = None):
    """
    Get list of available races in cache.
    
    Args:
        year: Optional year to filter
    
    Returns:
        list: Available race events
    """
    from fastf1 import events
    
    if year:
        return events.get_event_schedule(year)
    else:
        # Get all years from cache
        cache_years = [d for d in CACHE_DIR.iterdir() if d.is_dir() and d.name.isdigit()]
        all_events = []
        for y in cache_years:
            try:
                events_year = events.get_event_schedule(int(y.name))
                all_events.append(events_year)
            except:
                continue
        return pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()

if __name__ == "__main__":
    # Example usage
    df = get_race_data(2023, 22, 'HAM')
    
    if df is not None:
        print("\n--- First 5 Laps Preview ---")
        print(df.head())
        print("\n--- Tire Compounds Used ---")
        print(df['Compound'].value_counts())