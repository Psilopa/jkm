import requests, time
from pathlib import Path

IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
def defaultdownloader(url: str, sleeptime:int = 0, timeout: int = 1) -> bytes: 
    """Extract output filename from image URL path."""
    # Based on Mikko Heikkinen's read_specimens.py from MocoDigi
    try:
        # To avoid flooding the server, we do not rush here...
        time.sleep(sleeptime) 
        image_response = requests.get(
            url,
            headers=IMAGE_REQUEST_HEADERS,
            timeout=timeout,
        )
        image_response.raise_for_status()
        return image_response.content # Return raw data
    except requests.RequestException as exc:
        return None

if __name__ == "__main__":
    downloader("https://inaturalist-open-data.s3.amazonaws.com/photos/751707193/original.jpg")

