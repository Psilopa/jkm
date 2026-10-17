# -*- coding: utf-8 -*-
import time, logging, math, re, io, shutil
import validators
from pathlib import Path
import numpy as np
import cv2
from jkm.downloader import defaultdownloader
from jkm.errors import FileLoadingError
from urllib.parse import urlparse
import urllib.request, ssl # For web downloads

log = logging.getLogger() # Overwrite if needed

def is_existing_path(url): 
    "Verify that this url, if a local file url, corresponds to an accessible path"
    try:
        filepath = uri2path( url )
    except ValueError: return # Can't validate this
    dirpath= filepath.parent
    # Catch some error states
    if not dirpath.is_dir():                
        raise FileLoadingError(f"Cannot find directory {filepath},  skipping to next sample.")
    if not filepath.exists():
        raise FileLoadingError(f"Could not find file {filepath}, skipping.")

def list2printvalues(mylist):
    out = []
    for valuedict in mylist:
        out +=  valuedict.values()
    return "\n".join(out)
    
def json2printdict(json):
    if isinstance(json, str): json = jsonmodule.loads(json)
    # Reformat a JSON reply to for Table output
    rv = {}
    for key in json.keys():
        if isintance(json[key], list):
            rv[key] = list2printvalues(json[key])
        else: rv[key] = json[key]
    return rv    

def logtime(f,*a,**k):
    """monitor spent time in slow/heavy processes, output on debug level only"""
    t1 = time.time()
    r = f(*a,**k)    
    t2 = time.time()
    log.debug("\t\tTime spent in %s was %f" % (f.__name__,t2-t1))
    return r    

def monitor_disk_space(dir_name,limit,levels=[1,0.1,0.01]):
    """Monitor free disk space in given directory, warning at level[0], error at level[1], critical at level[2]"""
    freeb = shutil.disk_usage(dir_name).free
    feespace = (freeb/(1024**2), freeb/(1024**3)) # Free space in MB, GB
    if freeb < levels[0]*limit:        
        log.warning("Disk space low (free space %.0f MB (%.1f GB)" % feespace)
    elif freeb < levels[1]*limit:
        log.error("Disk space very low (free space %.0f MB (%.1f GB)" % feespace)
    elif freeb < levels[2]*limit:
        log.critical("Disk space critical (free space %.0f MB (%.1f GB)" % feespace)

def gammacorrect(img, gamma):
    lookUpTable = np.empty((1,256), np.uint8)
    for i in range(256):
        lookUpTable[0,i] = np.clip(math.pow(i / 255.0, gamma) * 255.0, 0, 255)
    return cv2.LUT(img, lookUpTable)

def shrink_to_maxdim(img,maxdim):
    md = max(img.shape)
    scale = min(1.0, maxdim/md)
    return cv2.resize(img,(0,0),fx=scale,fy=scale)
    
def save_img(fn,image): # Better error handling than the raw cv2 imwrite
    if isinstance(fn,Path): fn = str(fn)
    try: cv2.imwrite(fn,image)
    except SystemError as err: raise err

def img_from_file(imagestr):
        fnp = Path(imagestr)
        if not fnp.exists(): raise FileLoadingError("File %s does not exist" % fnp)
        if not fnp.is_file(): raise FileLoadingError("%s is not a file" % fnp)
        if fnp.is_reserved(): raise FileLoadingError("File %s is reserved" % fnp)
        return cv2.imread(str(fnp),cv2.IMREAD_UNCHANGED)
    
defcont = ssl.create_default_context()
defcont.check_hostname = False
defcont.verify_mode = ssl.CERT_NONE
def img_from_url(url, downloader = defaultdownloader, dlargs = [], dlkwords = {}):
    """Tries to return an image from a URI.

    If the needs to be downloaded, calls the optional downloader function
    like this downloader(url, *dlargs, **dlkwords). This allows for custom
    downloaders for various data sources.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme == 'file':
        return img_from_file(parsed_url.path)
    # OK, this is not a local file...
    if not downloader:
        raise FileLoadingError(f"Resource {url} is not local and we have no provided way to download it")
    # Try to use the provided downloader
    content = downloader(uri) # Should return a raw byte array
    print("type(content) = ", type(content) )
    arr = np.asarray(bytearray(content), dtype=np.uint8)
    return cv2.imdecode(arr, -1) # 'Load it as it is'

    
def load_img(image): #Loads image from image object or file
    """Loads an image (as a cv2 image) from a variety of sources.

    Accept
    - a Path
    - a IOBase stream (which is treated as an opened file with image data
    - 
    an image type
    """
    # Todo: add better Error handling (catch SystemError from and convert from FileError or like)
    if isinstance(image, Path): return img_from_file(image)
    elif isinstance(image, str): # Can be a path or a uri
        try:
            if Path(image).exists(): img_from_file(image) 
        except FileLoadingError: pass # Continue on failure to read as path
        imgstr = image.strip()
        if validators.url( imgstr ):  # Should be a valid URL as-is
            return img_from_url( imgstr )
    elif isinstance(image,io.IOBase):
        img = cv2.imdecode(image.read(),cv2.IMREAD_UNCHANGED)
    else:
        img = image # This is hopefully already a Image-type object ... test for numpy.ndarray ?    
    return img

def increaseTopContrast(image,greyrange):
    """Increase contast in the bright parts of the image.
    Assumes a grayscale image. greyrange = width of grayscale area between
    black and max_brightness."""
    maxi = np.amax(image)
    mini = max(0,maxi - greyrange)
    ret, ni = cv2.threshold(image,mini,maxi,cv2.THRESH_TOZERO)
    return ni

pattern_luomus1 = r"""([?P<url>dtnluomusfi,\.\s]{5,}) # id.luomus.fi or tun.fi plus errors
[\W69]*?   # Misc signs on line 1 (male/female sign + errors
(?P<ns>[A-Z\s]+?)  # namespace
[,\.]     # Literal point (or comma, error in OCR)
(?P<number>[0-9\s]+)  # serial
"""
reg1= re.compile(pattern_luomus1,re.VERBOSE)

pattern_luomus2 = r"""([?P<url>luomusfi1,\.\s]{5,})   # id.luomus.fi or tun.fi plus errors
[\W369Qgd\s|]*?   # A few misc signs on line 1 (male/female sign + errors
(?P<ns>[A-Z][A-Z\s]*?)  # namespace
[,\.:]     # Literal point (or comma, error in OCR)
(?P<number>[0-9\s]+)  # serial
"""
reg2= re.compile(pattern_luomus2,re.VERBOSE)

regs = (reg1,reg2)

def shortid_from_text(text):
    """Try to find identifier from image.

Returns the short form only! Assumes 0-1 matches!"""
    #text = re.sub("[\t\n\r\f\v]","",text)
    reslist = []
    for reg in regs:
        for res in reg.finditer(text):
            ns = res.group("ns").replace(" ","")
            ns = ns.strip()
            num = res.group("number").replace(" ","")
            num = num.strip()
            reslist.append("%s.%s" % (ns,num))
    return reslist
    
    
def safecopy(orig_path, target_path, overwrite = True):
    "Copy a file sort of safely."
    orig_path = Path(orig_path)
    target_path = Path(orig_path)
    log.debug(f"Trying to back up file from {orig_path} to {copy_path}")
    if  orig_path.exists() and orig_path.is_file():
        if not overwrite and target_path.exists():
            return False
        shutil.copy(orig_path, target_path)
        return True
    return False

def unique(s) :return tuple(set(s))

def quit_if_not_exists(pathname):
    if not pathname.exists():
        log.critical(f"Path {pathname} not found. Quitting.")
        sys.exit()


#  ---------------- URI to Path conversions ------------------
def path2uri(fpath):
    return fpath.as_uri() # THIS IS DEPRECATED
#    return urllib.request.pathname2url( str(fpath) ) 

def uri2path(url):
    return Path.from_uri(url) # Added in version 3.13.
#    return Path( urllib.request.url2pathname(url) )
