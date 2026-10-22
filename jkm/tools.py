# -*- coding: utf-8 -*-
import time, logging, math, re, io, shutil
import validators, json
from pathlib import Path
import numpy as np
import cv2
from jkm.downloader import defaultdownloader
from jkm.errors import FileLoadingError
from urllib.parse import urlparse, ParseResult, unquote
import urllib.request
log = logging.getLogger() # Overwrite if needed
# For typing
from jkm.typing import *

def as_existing_path(url: type_url) -> Path|None: 
    """Verify that this url, if a local file url, corresponds to an accessible path.

    Returns a Path on success. Raises a FileLoadingError on failure. """
    try:
        filepath = url2path( url )
    except ValueError:
        raise FileLoadingError(f"Turning {url} into a Path failed.") 
    # Catch some error states
    dirpath: Path = filepath.parent
    if not dirpath.is_dir(): 
        raise FileLoadingError(f"Cannot find directory {dirpath}.")
    if not filepath.exists():
        raise FileLoadingError(f"Could not find file {filepath}.")
    return filepath
    

def list2printvalues( mylist: Collection[dict] )-> str:
    "Prettyprints the values from a list of dictionaries."
    out: list = []
    for valuedict in mylist:
        out +=  valuedict.values()
    return "\n".join(out)
    
def json2printdict(jsondata: str | dict[str,Any] ) -> dict[str,Any]:
    "Converts a string with JSON data or a corresponding dictionary with prettyprinted content."
    # TODO: this is not pasticularly good
    if isinstance(jsondata, str):  jsondata = json.loads(jsondata) 
    # Reformat a JSON reply to for Table output
    rv: dict[str,str] = {}
    for key in jsondata.keys():
        if isinstance(jsondata[key], list):
            rv[key] = list2printvalues( jsondata[key] )
        else: rv[key] = jsondata[key]
    return rv

def logtime(func: Callable, *args: list, **kwargs: dict):
    """Logs the time spent ina function, output on debug level only.

    Arguments:
    func: a function
    args: list - arguments for function
    kwargs: dictionary - keyword arguments for function

    Return value:
    The return value for calling function with the given arguments.
    """
    t1: float = time.time()
    r = func(*args,**kwargs)    
    t2: float = time.time()
    log.debug("\t\tTime spent in %s was %f" % (func.__name__,t2-t1))
    return r    

def monitor_disk_space(dir_name: str | Path,
                       limit: int,
                       levels: list[float] = [1, 0.1, 0.01] ) -> None:
    """Monitor free disk space in given directory, warning at level[0], error at level[1], critical at level[2].

    Arguments:
    dir_name: string or Path - name of directory
    limit: int - lower acceptable limit
    levels: list or 3 ints
    """
    dir_name = str(dir_name)
    # shutil.disk_usage returns free space in bytes
    freeb: int = shutil.disk_usage(dir_name).free
    # This should probably convert to float!
    feespace: tuple[float,float] = (freeb/(1024**2), freeb/(1024**3)) # Free space in MB, GB
    if freeb < levels[0]*limit:        
        log.warning("Disk space low (free space %.0f MB (%.1f GB)" % feespace)
    elif freeb < levels[1]*limit:
        log.error("Disk space very low (free space %.0f MB (%.1f GB)" % feespace)
    elif freeb < levels[2]*limit:
        log.critical("Disk space critical (free space %.0f MB (%.1f GB)" % feespace)

def gammacorrect(img: type_image, gamma: float) -> type_image:
    lookUpTable: type_image = np.empty((1,256), np.uint8)
    for i in range(256):
        lookUpTable[0,i] = np.clip(math.pow(i / 255.0, gamma) * 255.0, 0, 255)
    return cv2.LUT(img, lookUpTable)

def shrink_to_maxdim(img: type_image, maxdim: int) -> type_image:
    current_maxdim: int = max(img.shape)
    scale: float = min(1.0, float(maxdim)/current_maxdim)
    return cv2.resize(img,(0,0),fx=scale,fy=scale)
    
def save_img(fn: str|Path, image: type_image) -> None: 
    # Better error handling than the raw cv2 imwrite
    if isinstance(fn,Path): fn = str(fn)
    try: cv2.imwrite(fn,image)
    except SystemError as err: raise err

def img_from_file(imagestr: str|Path) -> type_image | None:
        fnp = Path(imagestr)
        if not fnp.exists(): raise FileLoadingError("File %s does not exist" % fnp)
        if not fnp.is_file(): raise FileLoadingError("%s is not a file" % fnp)
        if fnp.is_reserved(): raise FileLoadingError("File %s is reserved" % fnp)
        return cv2.imread(str(fnp),cv2.IMREAD_UNCHANGED)
    
def img_from_url(url: str,
                 downloader: Callable = defaultdownloader,
                 dlargs:list = [], dlkwords:dict = {}) -> type_image | None:
    """Tries to return an image from a URI.

    If the needs to be downloaded, calls the optional downloader function
    like this downloader(url, *dlargs, **dlkwords). This allows for custom
    downloaders for various data sources.
    """
    try:
        filepath = url2path(url)
        return img_from_file( filepath )
    except FileLoadingError as err:
        pass # OK, this is not a local file...    
    if not downloader:
        raise FileLoadingError(f"Resource {url} is not local and we have no provided way to download it.")
    # Try to use the provided downloader
    content = downloader(url, *dlargs, **dlkwords) # Should return a raw byte array
    if content is None: 
        raise FileLoadingError(f"Could not download file {url}.")
    arr = np.asarray(bytearray(content), dtype=np.uint8)
    return cv2.imdecode(arr, -1) # 'Load it as it is'

    
def load_img(image: str|Path|io.IOBase|type_image) -> type_image | None: 
    """Loads an image (as a cv2 image) from a variety of sources.

    Accept
    - a string
    - a Path
    - a IOBase stream (which is treated as an opened file with image data
    - an numpy array (=a cv2 image in Python)
    """
    # Todo: add better Error handling (catch SystemError from and convert from FileError or like)
    if isinstance(image, Path): return img_from_file(image)
    elif isinstance(image, str): # Can be a path or a uri
        try:
            if Path(image).exists(): img_from_file(image) 
        except FileLoadingError: pass # Not a Path. 
        imgstr = image.strip()
        if validators.url( imgstr ):  # Should be a valid URL as-is
            return img_from_url( imgstr )
    elif isinstance(image,io.IOBase):
        return cv2.imdecode(image.read(),cv2.IMREAD_UNCHANGED)
    else:
        return image # This is hopefully already a Image-type object ... test for numpy.ndarray ?    

def increaseTopContrast(image: type_image, greyrange: int) -> type_image:
    """Increase contast in the bright parts of the image.
    Assumes a grayscale image. greyrange = width of grayscale area between
    black and max_brightness."""
    maxi: int = np.amax(image)
    mini: int = max(0,maxi - greyrange)
    ret, ni = cv2.threshold(image,mini,maxi,cv2.THRESH_TOZERO)
    return ni

pattern_luomus1: str = r"""([?P<url>dtnluomusfi,\.\s]{5,}) # id.luomus.fi or tun.fi plus errors
[\W69]*?   # Misc signs on line 1 (male/female sign + errors
(?P<ns>[A-Z\s]+?)  # namespace
[,\.]     # Literal point (or comma, error in OCR)
(?P<number>[0-9\s]+)  # serial
"""
reg1: re.Pattern = re.compile(pattern_luomus1,re.VERBOSE)

pattern_luomus2: str = r"""([?P<url>luomusfi1,\.\s]{5,})   # id.luomus.fi or tun.fi plus errors
[\W369Qgd\s|]*?   # A few misc signs on line 1 (male/female sign + errors
(?P<ns>[A-Z][A-Z\s]*?)  # namespace
[,\.:]     # Literal point (or comma, error in OCR)
(?P<number>[0-9\s]+)  # serial
"""
reg2: re.Pattern = re.compile(pattern_luomus2,re.VERBOSE)

regs: tuple[re.Pattern, re.Pattern] = (reg1,reg2)

def shortid_from_text(text: str) -> list[str]:
    """Try to find identifier from image. Returns the short form only!"""
    #text = re.sub("[\t\n\r\f\v]","",text)
    reslist: list = []
    for reg in regs:
        for res in reg.finditer(text):
            ns = res.group("ns").replace(" ","")
            ns = ns.strip()
            num = res.group("number").replace(" ","")
            num = num.strip()
            reslist.append("%s.%s" % (ns,num))
    return reslist
    
    
def safecopy(orig_path: Path, target_path: Path, overwrite:bool = True) -> bool:
    "Copy a file sort of safely."
    orig_path = Path(orig_path)
    target_path = Path(target_path)
    log.debug(f"Trying to back up file from {orig_path} to {target_path}")
    if  orig_path.exists() and orig_path.is_file():
        if not overwrite and target_path.exists():
            return False
        shutil.copy(orig_path, target_path)
        return True
    return False

def unique(s: list|tuple) ->tuple :return tuple(set(s))

#  ---------------- URL to Path conversions ------------------
def path2url(fpath: Path) -> str:    
    """Convert a Path to an URL."""
    return fpath.as_uri() # THIS IS DEPRECATED
#    return urllib.request.pathname2url( str(fpath) ) 

def url2path(url: str) -> Path:
    """Convert an URL to a Path."""
    # get path element from the URL
    urlpath = urllib.parse.urlparse( url ).path # Can fail
    # convert URL encoding (%20 for space etc.) back to originals
    pathstr = urllib.request.url2pathname( urlpath ) 
    return Path(pathstr)


# ----- string to XML preparation ---------------
#Based on an answer by John Machin on Stack Overflow (http://stackoverflow.com/users/84270/john-machin)
#http://stackoverflow.com/questions/8733233/filtering-out-certain-bytes-in-python

def isValidXMLChar(char):
  codepoint = ord(char)
  return 0x20 <= codepoint <= 0xD7FF or   \
         codepoint in (0x9, 0xA, 0xD) or  \
         0xE000 <= codepoint <= 0xFFFD or \
         0x10000 <= codepoint <= 0x10FFFF

def valid_xml_string(intext):
    return "".join(filter(isValidXMLChar, intext))
