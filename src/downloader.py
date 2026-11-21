import requests, time, logging
from pathlib import Path
# For typing
from .errors import FileLoadingError
#from .mytyping import * # For typing
from .meta import name as progname
log = logging.getLogger(progname) 

def defaultdownloader(url: type_url,
                      useragent:str  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                      sleeptime:int = 0,
                      timeout: int = 5) -> bytes|None: 
    """Extract output filename from image URL path."""
    # Based on Mikko Heikkinen's read_specimens.py from MocoDigi
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

