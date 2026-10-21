import requests, time
from pathlib import Path
# For typing
from jkm.typing import *
from jkm.errors import FileLoadingError

IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#        "AppleWebKit/537.36 (KHTML, like Gecko) "
#        "Chrome/120.0.0.0 Safari/537.36"
    )
}
def defaultdownloader(url: type_url,
                      sleeptime:int = 0,
                      timeout: int = 1) -> bytes|None: 
    """Extract output filename from image URL path."""
    # Based on Mikko Heikkinen's read_specimens.py from MocoDigi
    try:
        # To avoid flooding the server, we do not rush here...
        if sleeptime: time.sleep(sleeptime) 
        image_response = requests.get(
            url,
            headers=IMAGE_REQUEST_HEADERS,
            timeout=timeout,
        )
        # Check for failure
        image_response.raise_for_status() # 400 or 500 series errors
        if image_response.status_code != requests.codes.ok:
            raise FileLoadingError(f"Image download request failed with error code {FileLoadingError} and text {image_response.text}")
        return bytes(image_response.content) # Return raw data
    except (TypeError, requests.RequestException, requests.exceptions.HTTPError) as exc:
        raise FileLoadingError(exc)

