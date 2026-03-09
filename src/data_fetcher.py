"""
F1 data fetcher using FastF1 library.
"""

import fastf1
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Get the project root directory
CACHE_DIR = Path(__file__).parent.parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

# Enable FastF1 caching
fastf1.Cache.enable_cache(str(CACHE_DIR))

#===============================================================================
# DATA FETCHING FUNCTIONS
#===============================================================================

@st.cache_data(ttl=3600, show_spinner="Fetching F1 data...")
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

@st.cache_data(ttl=3600)
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
    
    # Test data quality
    for year in [1999, 2005, 2012, 2016, 2023]:
        icon, msg, score, color = check_data_quality(year)
        print(f"{year}: {icon} Score: {score}% - {msg}")
    
    # Test fetching data
    df = fetch_race_data(2023, 22, 'HAM')
    if df is not None:
        print(f"\nSuccessfully fetched {len(df)} laps for Hamilton at 2023 Abu Dhabi")
        print(f"Columns: {list(df.columns)}")