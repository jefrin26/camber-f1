"""
Live monitoring core module.
Handles real-time data fetching and processing for live sessions.
"""

import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
import pandas as pd
import logging
import numpy as np

# Import core modules
from src.data_fetcher import fetch_live_timing_data
from src.tire_model import calculate_degradation_delta, add_health_scores

logger = logging.getLogger(__name__)

class LiveMonitor:
    """
    Manages live timing monitoring for F1 sessions.
    Provides real-time updates and data processing.
    """
    
    def __init__(self):
        self.is_active = False
        self.is_paused = False
        self.last_update = None
        self.data = None
        self.processed_data = None
        self.driver_stats = {}
        self.trends = {}
        self.update_count = 0
        self.error_count = 0
        self._update_thread = None
        self._stop_flag = False
        self._lock = threading.RLock()
        
    def start(self, 
              drivers: List[str], 
              session: str,
              params: Dict,
              update_interval: int = 15,
              callback: Optional[Callable] = None):
        """
        Start live monitoring.
        
        Args:
            drivers: List of driver codes to monitor
            session: Session type ('R', 'Q', etc.)
            params: Model parameters for calculations
            update_interval: Seconds between updates
            callback: Optional callback function for updates
        """
        self.drivers = drivers
        self.session = session
        self.params = params
        self.update_interval = update_interval
        self.callback = callback
        self.is_active = True
        self.is_paused = False
        self._stop_flag = False
        self.error_count = 0
        
        logger.info(f"Live monitor started for drivers: {drivers}, session: {session}")
        
        # Start monitoring thread
        self._update_thread = threading.Thread(target=self._monitoring_loop)
        self._update_thread.daemon = True
        self._update_thread.start()
    
    def stop(self):
        """Stop live monitoring."""
        self.is_active = False
        self._stop_flag = True
        if self._update_thread:
            self._update_thread.join(timeout=2)
        logger.info("Live monitor stopped")
    
    def pause(self):
        """Pause live updates."""
        self.is_paused = True
        logger.info("Live monitor paused")
    
    def resume(self):
        """Resume live updates."""
        self.is_paused = False
        logger.info("Live monitor resumed")
    
    def _monitoring_loop(self):
        """Background thread for continuous monitoring."""
        while not self._stop_flag:
            if self.is_active and not self.is_paused:
                try:
                    success = self.update()
                    if success:
                        self.error_count = 0
                    else:
                        self.error_count += 1
                        
                    # Call callback if provided
                    if self.callback and self.processed_data is not None:
                        self.callback(self.get_status())
                        
                except Exception as e:
                    logger.error(f"Update error: {e}")
                    self.error_count += 1
            
            # Wait for next update
            for _ in range(self.update_interval):
                if self._stop_flag:
                    break
                time.sleep(1)
    
    def update(self) -> bool:
        """
        Fetch and process latest live data.
        
        Returns:
            bool: True if update successful
        """
        try:
            # Fetch live data
            raw_data = fetch_live_timing_data(self.drivers, self.session)
            
            if raw_data is None or len(raw_data) == 0:
                logger.debug("No live data available")
                return False
            
            # Process with tire model
            processed_data = calculate_degradation_delta(
                raw_data,
                fuel_decay_per_lap=self.params.get('fuel_decay', 2.5),
                time_penalty_per_kg=self.params.get('fuel_penalty', 0.035),
                benchmark_method=self.params.get('benchmark', 'fastest')
            )
            
            processed_data = add_health_scores(
                processed_data,
                max_degradation=self.params.get('max_degradation', 2.5)
            )
            
            # Update driver stats
            driver_stats = self._calculate_driver_stats(processed_data)
            
            # Update trends
            trends = self._calculate_trends(processed_data)
            
            # Update shared state with lock
            with self._lock:
                self.data = raw_data
                self.processed_data = processed_data
                self.driver_stats = driver_stats
                self.trends = trends
                self.last_update = datetime.now()
                self.update_count += 1
            
            logger.debug(f"Live update #{self.update_count} successful")
            return True
            
        except Exception as e:
            logger.error(f"Live update failed: {e}")
            return False
    
    def _calculate_driver_stats(self, processed_data: pd.DataFrame) -> Dict:
        """Calculate current statistics for each driver."""
        if processed_data is None or len(processed_data) == 0:
            return {}
        
        stats = {}
        for driver in processed_data['Driver'].unique():
            driver_data = processed_data[processed_data['Driver'] == driver]
            
            if len(driver_data) > 0:
                latest = driver_data.iloc[-1]
                
                # Calculate stint stats
                stint_data = driver_data[driver_data['Stint'] == latest['Stint']]
                
                stats[driver] = {
                    'lap': int(latest['LapNumber']),
                    'stint': int(latest['Stint']),
                    'compound': latest['Compound'],
                    'tyre_life': int(latest['TyreLife']),
                    'last_lap': latest['LapTimeSeconds'],
                    'health': latest['HealthScore'],
                    'degradation': latest['DegradationDelta'],
                    'best_lap': driver_data['LapTimeSeconds'].min(),
                    'avg_health': driver_data['HealthScore'].mean(),
                    'stint_laps': len(stint_data),
                    'stint_avg_degradation': stint_data['DegradationDelta'].mean()
                }
        
        return stats
    
    def _calculate_trends(self, processed_data: pd.DataFrame) -> Dict:
        """Calculate degradation trends for each driver."""
        if processed_data is None or len(processed_data) < 5:
            return {}
        
        trends = {}
        for driver in processed_data['Driver'].unique():
            driver_data = processed_data[processed_data['Driver'] == driver]
            
            if len(driver_data) >= 5:
                # Use last 5 laps for trend
                recent = driver_data.tail(5)
                
                # Simple linear trend
                x = list(range(len(recent)))
                y = recent['DegradationDelta'].values
                
                if len(x) > 1:
                    # Calculate slope using numpy
                    slope = np.polyfit(x, y, 1)[0]
                    
                    # Predict next lap degradation
                    next_degradation = y[-1] + slope
                    
                    trends[driver] = {
                        'degradation_rate': slope,
                        'trend_direction': 'increasing' if slope > 0.05 else 'stable' if slope > -0.05 else 'decreasing',
                        'next_predicted': next_degradation,
                        'laps_remaining': self._estimate_laps_remaining(driver_data, slope)
                    }
        
        return trends
    
    def _estimate_laps_remaining(self, driver_data: pd.DataFrame, slope: float) -> int:
        """Estimate laps remaining based on degradation trend."""
        if slope <= 0:
            return 99  # Not degrading
        
        if driver_data.empty:
            return 0
        
        current_degradation = driver_data['DegradationDelta'].iloc[-1]
        max_degradation = self.params.get('max_degradation', 2.5)
        
        # Calculate laps until max degradation
        if abs(slope) < 1e-10:  # Avoid division by zero
            return 99
        
        remaining = (max_degradation - current_degradation) / slope
        return max(0, int(remaining))
    
    def get_status(self) -> Dict:
        """Get current monitoring status."""
        return {
            'active': self.is_active,
            'paused': self.is_paused,
            'last_update': self.last_update,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'drivers': self.drivers,
            'session': self.session,
            'driver_stats': self.driver_stats,
            'trends': self.trends,
            'has_data': self.processed_data is not None
        }
    
    def get_latest_lap(self, driver: str) -> Optional[Dict]:
        """Get latest lap data for a specific driver."""
        if self.processed_data is None:
            return None
        
        driver_data = self.processed_data[self.processed_data['Driver'] == driver]
        if len(driver_data) == 0:
            return None
        
        latest = driver_data.iloc[-1]
        return {
            'lap_number': int(latest['LapNumber']),
            'lap_time': latest['LapTimeSeconds'],
            'compound': latest['Compound'],
            'tyre_life': int(latest['TyreLife']),
            'health': latest['HealthScore'],
            'degradation': latest['DegradationDelta'],
            'stint': int(latest['Stint'])
        }