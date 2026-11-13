import importlib, logging
log = logging.getLogger() # Overwrite if needed
# non-std common libraries
import cv2
# application-specific modules
from . import tools
from .errors import BarcodeError
from .mytyping import * # For type checking tools
# Dynamic  import in extractbarcodedata to allow for config fig-based import

# ENUM pseudoclasses
class barcodemodule:
    QREADER = "qreader"
    PYZBAR = "pyzbar"
    ALL = (QREADER, PYZBAR)
class barcodetype:
    QR = "QR"

pyzbar = QReader = None

class barcode:
    """A single barcode."""
    def __init__(self:Self):
        self.text = ""
        self.left = self.right = self.top= self.bottom = None
        self.rot = None # Rotation
        self.type = barcodetype.QR
        self.confidence = None
    @property
    def center(self:Self) -> tuple(int,inb):
        return ( (self.left+self.right)/2, (self.top+self.bottom)/2 )
    def __str__(self:Self):
        return f"Barcode '{self.text}' at {self.left}:{self.right} {self.top}:{self.bottom}"
    @classmethod
    def fromQReader(data):
        """Returns a barcode object build from a QReader detect_and_decode(image, return_detections = True)
        return data dictionary."""
        qr = barcode()
        qr.text = data[0]
        qr.left, self.top, self.right, self.bottom = data[1]['bbox_xyxy']
        self.confidence = data[1]['confidence']
        return qr

def _extract_class_pyzbar(greyimg:type_image, encoding:str|None=None) -> tuple[str, ...]:
    """Extract barcode data using PyZBar.
    
    Returns a list of found (nonempty) values. It nay contain duplicates.

    Arguments:
    greyimg: a image object (cv2 image, a  numpy array, or a file name)

    Keywords:
    encoding: encoding on the barcode content, if known.
    """
    barcodes = []
    # try qr recognition at different image sizes
    for maxdim in (200,600,2000,max(greyimg.shape)):
        smallimg = tools.shrink_to_maxdim(greyimg,maxdim) # Loads if greyimg is not a bitmap
        # TODO: CURRENTLY READS ONLY QRCODES
        barcodes = pyzbar.decode(smallimg, symbols=[pyzbar.ZBarSymbol.QRCODE])
        if barcodes or maxdim == max(greyimg.shape): break
    log.debug("Found %i barcode(s)" % len(barcodes))
    d = []
    for qr in barcodes:
        n = barcode()        
        n.text = qr.data
        n.left = qr.rect.left 
        n.right = qr.rect.left + qr.rect.width
        n.top = qr.rect.top
        n.bottom = qr.rect.top + qr.rect.height
        if encoding: n.text = n.text.decode(encoding) 
        d.append(n)
    return tuple(x for x in d if x.text) # Make sure the result is a list of non-empty string

def _extract_qreader(greyimg:type_image) -> tuple[str,...]:
    """Extract barcode data using QReader. Returns a list of found (nonempty) values. It may contain duplicates.
        
    Arguments:
    greyimg: a in image object (cv2 image, a  numpy array, or a file name)
    """
    try:
        qreader = QReader( model_size='l',min_confidence=0.05 )
        qrdicts = qreader.detect_and_decode(image=greyimg, return_detections=True)
        
        # Make sure the result is a list of non-empty strings (removes None values and empty strings)
        d = tuple(barcode.fromQReader(x) for x in qrdicts if x[0]) # Make sure the result is a list of non-empty string
    except ModuleNotFoundError as msg:
        # Some qreader installs fail due to a missing ultralytics.yolo package
        log.error(str(msg) + " Could not search for barcodes.")
        d = tuple() # Return empty value
    return d
    
def extractbarcodes(image:type_image,
                       qrpackage:str,
                       increasecontast:bool=False,
                       greyrange:int=50,
                       encoding:str|None=None) -> tuple[str,...]:
    """Extract barcode data from an image. 
    
    Returns a tuple of barcode class instances.
    
    Arguments: 
    image -- Accepts either a filename, a file object, opencv images. Should also work with PIL or nympy image arrays.
    qrpackage -- name of barcode decoding backage to be used: see constants ONST_PYZBAR & CONST_QREADER.
    increasecontast -- if True, calls tools.increaseTopContrast with greyrange as the parameter.
    greyrange -- see above.
    encoding -- None or a name for the enconding used in decoding the barcode byte stream to text.
    """
    global QReader, pyzbar
    if qrpackage not in barcodemodule.ALL:
        raise BarcodeError(f"Unknown barcode reader tool '{qrpackage}'")
#    img = tools.load_img(image)
    img = image
    greyimg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if increasecontast:
        greyimg = tools.increaseTopContrast(greyimg,greyrange)
    if qrpackage == barcodemodule.PYZBAR:
        if not pyzbar: 
            importlib.import_module("pyzbar")
            from pyzbar import pyzbar
        d = _extract_class_pyzbar(greyimg, encoding)    
    elif qrpackage == barcodemodule.QREADER:
        if not QReader: 
            QReader = importlib.import_module("qreader").QReader
        d = _extract_qreader(greyimg)
    return d

def extractbarcodestrings(image:type_image,
                       qrpackage:str,
                       increasecontast:bool=False,
                       greyrange:int=50,
                       encoding:str|None=None) -> tuple[str,...]:
    """Extract barcode string data from an image. 
    
    Arguments: see extractbarcodes.
    """
    barcodes = extractbarcodes(image,qrpackage,increasecontast,greyrange,encoding)
    return tuple(b.text for b in barcodes)

