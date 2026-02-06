import logging, re,  sys
import importlib
# non-std common libraries
import cv2

# application-specific modules
import jkm.tools as tools
from jkm.errors import BarcodeError
# Dynamic  import in extractbarcodedata to allow for config fig-based import
CONST_QREADER = "qreader"
CONST_PYZBAR = "pyzbar"
pyzbar = QReader = None

log = logging.getLogger() # Overwrite if needed

def _extract_pyzbar(greyimg, encoding=None):
    barcodes = []
    # try qr recognition at different image sizes
    for maxdim in (200,600,2000,max(greyimg.shape)):
        smallimg = tools.shrink_to_maxdim(greyimg,maxdim)
        barcodes = pyzbar.decode(smallimg, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes or maxdim == max(greyimg.shape): break
    log.debug("Found %i barcode(s)" % len(barcodes))
    d = []
    for qr in barcodes:
        bkd = qr.data
        if encoding: bkd = bkd.decode(encoding) 
        d.append(bkd)
    return [x for x in d if x] # Make sure the result is a list of non-empty string

def _extract_qreader(greyimg):
    try:
        qreader = QReader( model_size='l',min_confidence=0.05 )
        decoded_text = qreader.detect_and_decode(image=greyimg)
        # Make sure the result is a list of non-empty strings (removes None values and empty strings)
        d = [x for x in decoded_text if x]
    except ModuleNotFoundError as msg:
        # qreader install on my computer lacks the ultralytics.yolo package
        log.warning(msg)
        d = []
    return d # Returns a tuple of strings

def extractbarcodedata(image, qrpackage, increasecontast=False,
                       greyrange=50,  encoding=None):
    "Is decite is not None, it is assumed to be a name for the enconding used in decoding the barcode byte stream to text"

    "Accepts either a filename, a file object, opencv images. Should also work with PIL or nympy image arrays."
    global QReader, pyzbar
    if qrpackage not in (CONST_QREADER, CONST_PYZBAR):
        log.critical(f"Unknown barcode reader tool '{qrpackage}'")
        sys.exit()
    img = tools.load_img(image)
    greyimg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if increasecontast: greyimg = tools.increaseTopContrast(greyimg,greyrange)
    if qrpackage == CONST_PYZBAR:
        if not pyzbar: 
            importlib.import_module("pyzbar")
            from pyzbar import pyzbar
        d = _extract_pyzbar(greyimg, encoding)    
    elif qrpackage == CONST_QREADER:
        if not QReader: 
            QReader = importlib.import_module("qreader").QReader
        d = _extract_qreader(greyimg)
    # else: should not happen as tested above
    return d

def sampleids(data):
    # Add CETAF verification here too...
    # read: a list of strings
    # return a list of (namespace,id) tuples of all detected labels
    sids = []
    reg1 = re.compile("/([A-Z0-9]+.[0-9-]+)",re.IGNORECASE)
    reg2 = re.compile("([A-Z0-9]+.[0-9-]+)",re.IGNORECASE)
    log.debug("Trying to find CETAF Identifiers in %s" % data)
    for l in data:
        m = reg1.search(l)
        if m:            
            log.debug("Found CETAF identifier with end value %s" % m.group(1))
            sids.append(m.group(1))
        else:
            m = reg2.search(l)
            if m:            
                log.debug("Found short identifier with end value %s" % m.group(1))
                sids.append(m.group(1))
    if len(sids) == 0: raise BarcodeError("Sample ID format unrecognised.")
    if len(sids) > 1:
        log.error("Several barcodes in image. Handling of this situation not supported.")
        sys.exit()
    return sids
