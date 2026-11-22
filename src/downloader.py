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


# Note: if we wanted to avoid in-memory caching, or time-based purging, we could use the requests-cache module.

sleeptime = 0
timeout = 10
useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" # Default UA. Can be used from calling code as a module attribute

# To avoid duplicate downloads, keep the last 3 requests in memory
@lru_cache(maxsize=3)
def cachedresponse(url: type_url) -> requests.Response:
    """A version of requests.get() with a simple 3-item cache."""
    return requests.get( url, headers={ "useragent":useragent }, timeout=timeout)

def cachedownloader(url: type_url, clear_cache:bool = False) -> bytes|None:
    """Download raw byte content. Keeps an in-memory cache of the last 3 calls."""
    # Based on Mikko Heikkinen's read_specimens.py from MocoDigi
    try:
        # To avoid flooding the server, we do not rush here...
        if sleeptime: time.sleep(sleeptime)
        if clear_cache: cachedresponse.cache_clear()
        image_response = cachedresponse(url)
        log.debug(f"cachedresponse() cache statistics: {cachedresponse.cache_info()}")
        # Check for failure
        image_response.raise_for_status() # 400 or 500 series errors
        if image_response.status_code != requests.codes.ok:
            raise FileLoadingError(f"Image download request failed with error code {FileLoadingError} and text {image_response.text}")
        return bytes(image_response.content) # Return raw data
    except (TypeError, requests.RequestException, requests.exceptions.HTTPError) as exc:
        raise FileLoadingError(exc)
