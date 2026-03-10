"""
F1 data fetcher using FastF1 library.
"""

import fastf1
import pandas as pd
import logging
from datetime import datetime
import streamlit as st

# Import cache manager for cache operations
from src.cache_manager import (
    CACHE_DIR,
    get_cache_size,
    clear_old_cache,
    clear_session_cache,
    clear_all_cache,
    list_cache_contents,
    get_cache_stats
)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Enable FastF1 caching (imported from cache_manager)
fastf1.Cache.enable_cache(str(CACHE_DIR))

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
            f"High Quality Data ({year}) - Full telemetry, tire compounds, and accurate lap times available",
            100,
            "#00ff00"
        )
    elif year >= 2014:
        return (
            "⚠️", 
            f"Moderate Quality Data ({year}) - Hybrid era: Basic telemetry available, tire compound data may be limited",
            75,
            "#ffaa00"
        )
    elif year >= 2010:
        return (
            "⚠️⚠️", 
            f"Limited Data ({year}) - Pre-hybrid era: Lap times available, limited telemetry, tire data may be incomplete",
            50,
            "#ff6600"
        )
    elif year >= 2000:
        return (
            "⚠️⚠️⚠️", 
            f"Basic Data Only ({year}) - Vintage era: Lap times and basic results available, no tire compound information",
            25,
            "#ff3300"
        )
    else:
        return (
            "❌", 
            f"Very Limited Data ({year}) - Historical data: May only have race results, lap times may be incomplete",
            10,
            "#ff0000"
        )

@st.cache_data(ttl=3600, max_entries=50, persist=False)
def get_drivers_for_race(year, round_num, session_type='R'):
    """
    Get list of drivers for a specific race.
    
    Args:
        year: Season year
        round_num: Race round number
        session_type: Session type ('R' for Race, 'Q' for Qualifying, etc.)
    
    Returns:
        list: Sorted list of driver codes
    """
    try:
        session = fastf1.get_session(year, round_num, session_type)
        session.load()
        
        drivers = []
        
        # Method 1: Try to get drivers from session.results
        try:
            if hasattr(session, 'results') and session.results is not None and len(session.results) > 0:
                drivers = session.results['Abbreviation'].tolist()
        except Exception as e:
            logger.debug(f"Method 1 failed: {e}")
        
        # Method 2: Try session.drivers (list of driver IDs)
        if not drivers:
            try:
                if hasattr(session, 'drivers') and session.drivers:
                    drivers = list(session.drivers)
            except Exception as e:
                logger.debug(f"Method 2 failed: {e}")
        
        # Method 3: Try to get driver names from the session
        if not drivers:
            try:
                if hasattr(session, 'driver') and session.driver:
                    drivers = list(session.driver.keys())
            except Exception as e:
                logger.debug(f"Method 3 failed: {e}")
        
        # Method 4: Try to get drivers from session.laps
        if not drivers:
            try:
                if hasattr(session, 'laps') and session.laps is not None:
                    drivers = session.laps['Driver'].unique().tolist()
            except Exception as e:
                logger.debug(f"Method 4 failed: {e}")
        
        # If still no drivers, try loading just the session data again
        if not drivers:
            try:
                session = fastf1.get_session(year, round_num, session_type)
                session.load(laps=False, telemetry=False, weather=False)
                if hasattr(session, 'results') and session.results is not None:
                    drivers = session.results['Abbreviation'].tolist()
            except Exception as e:
                logger.debug(f"Method 5 failed: {e}")
        
        # If still no drivers, return empty list (let app handle fallback)
        if not drivers:
            logger.warning(f"No drivers found for {year} R{round_num} {session_type}")
            return []
        
        # Ensure all drivers are uppercase strings
        drivers = [str(d).upper() for d in drivers if d]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_drivers = []
        for d in drivers:
            if d not in seen:
                seen.add(d)
                unique_drivers.append(d)
        
        return sorted(unique_drivers)
    
    except Exception as e:
        logger.warning(f"Could not fetch drivers for {year} R{round_num}: {e}")
        # Return empty list to trigger fallback in app
        return []

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