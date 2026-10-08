# -*- coding: utf-8 -*-
import time,  logging,  ast,  math,  re,  io,  shutil, os 
import time,  logging,  ast,  math,  re,  io,  shutil, os 
from pathlib import Path
import numpy as np
import cv2
from jkm.errors import FileLoadingError

log = logging.getLogger() # Overwrite if needed
LOG_FILE_ENCODING = "utf8"

class ColorFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    white = "\x1b[0m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    def __init__(self, formatstr):
#        formatstr = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)" 
        self.FORMATS = {
            logging.DEBUG: self.grey + formatstr + self.reset,
            logging.INFO: self.white + formatstr + self.reset,
            logging.WARNING: self.yellow + formatstr + self.reset,
            logging.ERROR: self.red + formatstr + self.reset,
            logging.CRITICAL: self.bold_red + formatstr + self.reset,
        }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
            
def setup_logging(name, debug = False):
    """Set up logging services"""
    os.system('color')  # Ask system console to display color if available
    log = logging.getLogger(name)
    if debug: log.setLevel(logging.DEBUG)
    else: log.setLevel(logging.INFO)
    # To console
    chc = logging.StreamHandler( )
    log.addHandler(chc)
    # To log file
    chf = logging.FileHandler(f"{name}.log",  encoding=LOG_FILE_ENCODING)
    if debug: chf.setLevel(logging.DEBUG)
    else: chf.setLevel(logging.INFO)
    log.addHandler(chf)
#    simpleformat = '%(message)s'
#    for handler in log.handlers[:]: handler.setFormatter(ColorFormatter(simpleformat))
#    log.info("\n") # Print some empty lines using a simplified format
    logformat = '%(levelname)s: %(message)s [%(asctime)s]'
    for handler in log.handlers[:]: handler.setFormatter(ColorFormatter(logformat))
    if debug: log.info("Logging set up for debug.")
    else: log.info("Logging set up for not debugging data.")
    return log

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

def logtime(f,*a,**k):
    """monitor spent time in slow/heavy processes, output on debug level only"""
    t1 = time.time()
    r = f(*a,**k)    
    t2 = time.time()
    log.debug("\t\tTime spent in %s was %f" % (f.__name__,t2-t1))
    return r    

def string2list(instr):
    return ast.literal_eval(instr.strip())

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

def load_img(image): #Loads image from image object or file
    # Todo: add better Error handling (catch SystemError from and convert from FileError or like)
    if isinstance(image,str)or isinstance(image,Path):
        fnp = Path(image)
        if not fnp.exists(): raise FileLoadingError("File %s does not exist" % fnp)
        if not fnp.is_file(): raise FileLoadingError("%s is not a file" % fnp)
        if fnp.is_reserved(): raise FileLoadingError("File %s is reserved" % fnp)
        img = cv2.imread(str(fnp),cv2.IMREAD_UNCHANGED)
    elif isinstance(image, io.IOBase):
        img = cv2.imdecode(image.read(),cv2.IMREAD_UNCHANGED)
    else:
        img = image # This is hopefully already a Image-type object ... test for numpy.ndarray ?    
    if img is None: raise FileLoadingError("Loading file %s failed, reason not known" % image) 
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
#    print(text)
    reslist = []
    for reg in regs:
        for res in reg.finditer(text):
            ns = res.group("ns").replace(" ","")
            ns = ns.strip()
            num = res.group("number").replace(" ","")
            num = num.strip()
            reslist.append("%s.%s" % (ns,num))
    return reslist
    
    
def backup_file(orig_path,  copy_path):
    log.debug(f"Trying to back up file from {orig_path} to {copy_path}")
    if  orig_path.exists() and orig_path.is_file():  
        shutil.copy(orig_path,  copy_path)
    return True
