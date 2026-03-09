"""
F1 data fetcher using FastF1 library.
"""

import fastf1
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import streamlit as st
import time
import shutil
import os

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Get the project root directory
CACHE_DIR = Path(__file__).parent.parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

# Enable FastF1 caching
fastf1.Cache.enable_cache(str(CACHE_DIR))

#===============================================================================
# CACHE MANAGEMENT FUNCTIONS
#===============================================================================

def get_cache_size():
    """Get the size of the cache directory in MB and file count."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return {'size_mb': 0, 'file_count': 0}
    
    total_size = 0
    file_count = 0
    for file in cache_dir.rglob('*'):
        if file.is_file():
            total_size += file.stat().st_size
            file_count += 1
    
    return {
        'size_mb': total_size / (1024 * 1024),
        'file_count': file_count
    }

def clear_old_cache(max_age_days=7):
    """Clear cache files older than max_age_days."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return 0
    
    current_time = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60
    
    deleted_count = 0
    for file in cache_dir.rglob('*'):
        if file.is_file():
            file_age = current_time - file.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    file.unlink()
                    deleted_count += 1
                    print(f"Deleted old file: {file}")
                except Exception as e:
                    print(f"Could not delete {file}: {e}")
    
    # Clean up empty directories
    for dir_path in cache_dir.rglob('*'):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            try:
                dir_path.rmdir()
                print(f"Removed empty directory: {dir_path}")
            except:
                pass
    
    return deleted_count

def clear_session_cache():
    """Clear only the current session's temporary cache."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return 0
    
    deleted_count = 0
    
    # Clear temporary files by extension
    temp_extensions = ['.npy', '.tmp', '.part', '.temp', '.pickle', '.pkl', '.cache']
    for ext in temp_extensions:
        for file in cache_dir.rglob(f'*{ext}'):
            try:
                if file.is_file():
                    file.unlink()
                    deleted_count += 1
                    print(f"Deleted temp file: {file}")
            except Exception as e:
                print(f"Could not delete {file}: {e}")
    
    # Clear fastf1 temp directories
    for item in cache_dir.iterdir():
        if item.is_dir() and ('fastf1' in item.name or 'temp' in item.name):
            try:
                shutil.rmtree(item)
                deleted_count += 1
                print(f"Deleted directory: {item}")
            except Exception as e:
                print(f"Could not delete {item}: {e}")
    
    return deleted_count

def clear_all_cache():
    """Clear all cache (dangerous - use with caution)."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return False
    
    deleted_count = 0
    try:
        # Delete all files and directories inside cache
        for item in cache_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    deleted_count += 1
                    print(f"Deleted file: {item}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_count += 1
                    print(f"Deleted directory: {item}")
            except Exception as e:
                print(f"Could not delete {item}: {e}")
        
        # Re-enable cache after clearing
        fastf1.Cache.enable_cache(str(cache_dir))
        return deleted_count
    except Exception as e:
        print(f"Error clearing all cache: {e}")
        return False

def list_cache_contents(limit=20):
    """List contents of cache directory for debugging."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return []
    
    contents = []
    for i, item in enumerate(cache_dir.rglob('*')):
        if i >= limit:
            break
        if item.is_file():
            size_kb = item.stat().st_size / 1024
            mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            contents.append({
                'name': item.name,
                'path': str(item.relative_to(cache_dir)),
                'size_kb': round(size_kb, 2),
                'modified': mtime
            })
    
    return contents

def get_cache_stats():
    """Get detailed cache statistics."""
    cache_dir = Path(__file__).parent.parent / 'cache'
    if not cache_dir.exists():
        return {}
    
    total_size = 0
    file_count = 0
    by_extension = {}
    
    for file in cache_dir.rglob('*'):
        if file.is_file():
            size = file.stat().st_size
            total_size += size
            file_count += 1
            
            ext = file.suffix or 'no_extension'
            by_extension[ext] = by_extension.get(ext, 0) + 1
    
    return {
        'total_size_mb': total_size / (1024 * 1024),
        'file_count': file_count,
        'by_extension': by_extension
    }

#===============================================================================
# DATA FETCHING FUNCTIONS
#===============================================================================

@st.cache_data(ttl=3600, show_spinner="Fetching F1 data...", max_entries=20)
def fetch_race_data(year, round_num, driver, session_type='R'):
    """
    Fetch race data for a specific driver.
    
    Args:
        year: Season year
        round_num: Race round number
        driver: Driver abbreviation (e.g., 'VER', 'HAM')
        session_type: Session type ('R' for Race, 'Q' for Qualifying, etc.)
    
    Returns:
        pd.DataFrame: Cleaned dataframe with lap data
    """
    try:
        # Clear old cache occasionally (once per session)
        if 'cache_cleaned' not in st.session_state:
            clear_old_cache(max_age_days=7)
            st.session_state['cache_cleaned'] = True
        
        session = fastf1.get_session(year, round_num, session_type)
        session.load()
        
        laps = session.laps.pick_drivers([driver])
        
        if len(laps) == 0:
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
        
        return data.reset_index(drop=True)
    
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

@st.cache_data(ttl=3600, max_entries=5)
def get_available_races():
    """
    Get list of available races from FastF1.
    
    Returns:
        pd.DataFrame: DataFrame with available races
    """
    try:
        current_year = datetime.now().year
        years = list(range(2000, current_year + 1))
        
        race_schedule = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, year in enumerate(years):
            status_text.text(f"Loading {year} calendar...")
            try:
                events = fastf1.get_event_schedule(year)
                for _, event in events.iterrows():
                    race_schedule.append({
                        'Year': year,
                        'Round': event['RoundNumber'],
                        'Event': event['EventName'],
                        'Country': event['Country'],
                        'Date': event['EventDate']
                    })
            except Exception:
                # Skip years with no data
                continue
            
            progress_bar.progress((i + 1) / len(years))
        
        progress_bar.empty()
        status_text.empty()
        
        df = pd.DataFrame(race_schedule)
        
        if df.empty:
            st.warning("No race data found. Falling back to 2018-2024 range.")
            years = list(range(2018, current_year + 1))
            race_schedule = []
            for year in years:
                try:
                    events = fastf1.get_event_schedule(year)
                    for _, event in events.iterrows():
                        race_schedule.append({
                            'Year': year,
                            'Round': event['RoundNumber'],
                            'Event': event['EventName'],
                            'Country': event['Country'],
                            'Date': event['EventDate']
                        })
                except:
                    continue
            return pd.DataFrame(race_schedule)
        
        return df
        
    except Exception as e:
        st.warning(f"Could not fetch race schedule: {e}")
        fallback_years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
        race_schedule = []
        for year in fallback_years:
            try:
                events = fastf1.get_event_schedule(year)
                for _, event in events.iterrows():
                    race_schedule.append({
                        'Year': year,
                        'Round': event['RoundNumber'],
                        'Event': event['EventName'],
                        'Country': event['Country'],
                        'Date': event['EventDate']
                    })
            except:
                continue
        return pd.DataFrame(race_schedule)

#===============================================================================
# DATA QUALITY FUNCTIONS
#===============================================================================

def check_data_quality(year):
    """
    Check data quality and return appropriate warnings based on year.
    
    Args:
        year: The selected year
    
    Returns:
        tuple: (warning_level, warning_message, data_quality_score, color)
    """
    current_year = datetime.now().year
    
    if year >= 2018:
        return (
            "✅", 
            f"**High Quality Data** ({year}) - Full telemetry, tire compounds, and accurate lap times available",
            100,
            "#00ff00"
        )
    elif year >= 2014:
        return (
            "⚠️", 
            f"**Moderate Quality Data** ({year}) - Hybrid era: Basic telemetry available, tire compound data may be limited",
            75,
            "#ffaa00"
        )
    elif year >= 2010:
        return (
            "⚠️⚠️", 
            f"**Limited Data** ({year}) - Pre-hybrid era: Lap times available, limited telemetry, tire data may be incomplete",
            50,
            "#ff6600"
        )
    elif year >= 2000:
        return (
            "⚠️⚠️⚠️", 
            f"**Basic Data Only** ({year}) - Vintage era: Lap times and basic results available, no tire compound information",
            25,
            "#ff3300"
        )
    else:
        return (
            "❌", 
            f"**Very Limited Data** ({year}) - Historical data: May only have race results, lap times may be incomplete",
            10,
            "#ff0000"
        )

def get_feature_availability(year):
    """
    Get detailed feature availability for a given year.
    
    Args:
        year: The selected year
    
    Returns:
        dict: Dictionary of features and their availability
    """
    return {
        'Lap Times': year >= 1950,
        'Tire Compounds': year >= 2011,  # Pirelli era started 2011
        'Full Telemetry': year >= 2018,
        'Speed Traps': year >= 2010,
        'Weather Data': year >= 2000,
        'Driver Details': year >= 1990,
        'Position Data': year >= 2000,
        'Pit Stop Data': year >= 2010,
        'Sector Times': year >= 2010,
        'ERS Data': year >= 2014,
        'Throttle Data': year >= 2018,
        'DRS Data': year >= 2011,
    }

#===============================================================================
# TEST FUNCTION
#===============================================================================

if __name__ == "__main__":
    # Test the functions
    print("Testing data fetcher...")
    
    # Test cache functions
    cache_info = get_cache_size()
    print(f"\nCache size: {cache_info['size_mb']:.2f} MB, Files: {cache_info['file_count']}")
    
    # List cache contents
    print("\nCache contents (first 10 files):")
    for item in list_cache_contents(10):
        print(f"  - {item['path']} ({item['size_kb']} KB)")
    
    # Test data quality
    for year in [1999, 2005, 2012, 2016, 2023]:
        icon, msg, score, color = check_data_quality(year)
        print(f"{year}: {icon} Score: {score}% - {msg}")
    
    # Test fetching data
    df = fetch_race_data(2023, 22, 'HAM')
    if df is not None:
        print(f"\nSuccessfully fetched {len(df)} laps for Hamilton at 2023 Abu Dhabi")
        print(f"Columns: {list(df.columns)}")