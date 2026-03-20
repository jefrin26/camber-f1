"""
Cache management module for F1 data.
Provides centralized cache handling for FastF1 and temporary files.
"""

import fastf1
import time
import shutil
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

#===============================================================================
# CACHE DIRECTORY SETUP
#===============================================================================

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
                    logger.info(f"Deleted old file: {file}")
                except Exception as e:
                    logger.warning(f"Could not delete {file}: {e}")
    
    # Clean up empty directories
    for dir_path in cache_dir.rglob('*'):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            try:
                dir_path.rmdir()
                logger.info(f"Removed empty directory: {dir_path}")
            except Exception as e:
                logger.warning(f"Could not remove empty directory {dir_path}: {e}")
    
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
                    logger.info(f"Deleted temp file: {file}")
            except Exception as e:
                logger.warning(f"Could not delete {file}: {e}")
    
    # Clear fastf1 temp directories
    for item in cache_dir.iterdir():
        if item.is_dir() and ('fastf1' in item.name or 'temp' in item.name):
            try:
                shutil.rmtree(item)
                deleted_count += 1
                logger.info(f"Deleted directory: {item}")
            except Exception as e:
                logger.warning(f"Could not delete {item}: {e}")
    
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
                    logger.info(f"Deleted file: {item}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_count += 1
                    logger.info(f"Deleted directory: {item}")
            except Exception as e:
                logger.warning(f"Could not delete {item}: {e}")
        
        # Re-enable cache after clearing
        fastf1.Cache.enable_cache(str(cache_dir))
        return deleted_count
    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
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

