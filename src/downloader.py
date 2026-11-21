import requests
import time
import logging
from functools import lru_cache
from pathlib import Path
# For typing
from .errors import FileLoadingError
#from .mytyping import * # For typing
from .meta import name as progname
log = logging.getLogger(progname) 

n_downloaded = 0
def defaultdownloader(url: type_url,
                      useragent:str  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      sleeptime:int = 0,
                      timeout: int = 5) -> bytes|None: 
    """Download raw byte content."""
    # Based on Mikko Heikkinen's read_specimens.py from MocoDigi
    global n_downloaded
    n_downloaded += 1
    log.debug(f"defaultdownloader() call count: {n_downloaded}")
    try:
        # To avoid flooding the server, we do not rush here...
        if sleeptime: time.sleep(sleeptime) 
        image_response = requests.get(
            url,
            headers={ "useragent":useragent },
            timeout=timeout,
        )
        # Check for failure
        image_response.raise_for_status() # 400 or 500 series errors
        if image_response.status_code != requests.codes.ok:
            raise FileLoadingError(f"Image download request failed with error code {FileLoadingError} and text {image_response.text}")
        return bytes(image_response.content) # Return raw data
    except (TypeError, requests.RequestException, requests.exceptions.HTTPError) as exc:
        raise FileLoadingError(exc)

@lru_cache(maxsize=3)
def cachingdownloader(url: type_url,
                      useragent:str  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      sleeptime:int = 0,
                      timeout: int = 5) -> bytes|None:
    """Download raw byte content. Keeps an in-memory cache of the last 3 calls."""    
    return defaultdownloader(url, useragent, sleeptime, timeout)

