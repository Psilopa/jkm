import logging, re,  sys
# non-std common libraries
import cv2

# application-specific modules
import jkm.tools as tools
from jkm.errors import BarcodeError
from pyzbar import pyzbar # Barcode processing

log = logging.getLogger() # Overwrite if needed

def extractbarcodedata(image,increasecontast=False,greyrange=50,  encoding=None):
    "Is decite is not None, it is assumed to be a name for the enconding used in decoding the barcode byte stream to text"

    "Accepts either a filename, a file object, opencv images. Should also work with PIL or nympy image arrays."
    img = tools.load_img(image)
    greyimg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if increasecontast: greyimg = tools.increaseTopContrast(greyimg,greyrange)
    # try qr recognition at different image sizes
    barcodes = []
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
