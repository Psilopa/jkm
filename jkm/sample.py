from abc import ABC
from pathlib import Path
import datetime,  logging,  os
#import  pickle
import cv2
import jsonpickle
import jkm.metadata
import jkm.ocr
import jkm.tools

log = logging.getLogger() # Overwrite if needed
deg2rotcode = {90: cv2.ROTATE_90_CLOCKWISE,
               180: cv2.ROTATE_180,
               270: cv2.ROTATE_90_COUNTERCLOCKWISE}

#------------------------------------------------------------------------------------------------------    
# Helper functions
def getFileCreationDateTime(fn):
    # Does not work well on POSIX systems, which return the last modified date for getctime
    timestamp =  os.path.getctime(fn)
    return datetime.datetime.fromtimestamp(timestamp)

def create_new_image(imgtype): 
    "Create a new SampleImage subclass instance based on the requested type"
    if imgtype.lower().strip() == 'label': return LabelImage()
    if imgtype.lower().strip() == 'specimen': return SpecimenImage()
#------------------------------------------------------------------------------------------------------    
class SampleBase(ABC):
    def __init__(self, time = None): 
        if not time: self._time = datetime.datetime.now()
        else: self._time = time
        self.name = str(self) # TODO: replace with better names in subclasses, should use timestamp or camera name
    @property
    def time(self):  return self._time
    def encodeJSON(self):
        jsonpickle.set_preferred_backend('json')
        jsonpickle.set_encoder_options("json", ensure_ascii=False,  indent=2)        
        return jsonpickle.encode(self)
    @staticmethod
    def fromJSONfile(fn):
        with open(fn) as f:
            return  jsonpickle.decode(f.read())
#------------------------------------------------------------------------------------------------------    
class SampleEvent(SampleBase):
    "Container for 0+ photos of an sample and event-level metadata."
    def __init__(self,  time = None):
        super().__init__(time)
        self._imagelist = [] # List of SamplePhoto subclass instances
        self.prefix  = "" # Common file name prefix
#        self.basepath = "" # Common data directory
        self.datapath = "" # Data directory for this record
        self.meta = jkm.metadata.EventMetadata() # Event-level metadata
    @property
    def imagelist(self):  return self._imagelist
    @property
    def filelist(self):
        # INCOMPLETE IMPLEMENTATION, ONLY IMAGE FILES
        filelist = [Path(x.filename) for x in self._imagelist]
        return tuple(filelist) 
    @staticmethod
    def fromJPGfile(imgfile, conf, camname="generic_camera"): # Assumes jpg file name is metadata file name
        log.debug("Creating sample data from JPEG image and config file metadata")
        itime = getFileCreationDateTime(imgfile)
        imgfile = Path(imgfile)
        image = CombinedImage(camname, fn = imgfile)
        # Extract creating time from JPG and use it as the Sample event time        
        s = SampleEvent( time = itime )
        s.copyMetadatafFomConf(conf,  no_new_directiories=True)
        s.datapath = imgfile.parent
        s.addImage(image)
        s.prefix = imgfile.stem
        return s
    def writeMetaJSON(self,  extension = ".json"): 
        "Save SampleEvent metadata to a file"
        for img in self._imagelist: img.unloadImageData()
        metafn = self.datapath / "".join((self.prefix,extension))
        log.info(f"Writing metadata to file {metafn}")
        with metafn.open("w",encoding="utf8") as metaf:
            metaf.write(self.encodeJSON())
    def copyMetadatafFomConf(self, configobject,  no_new_directiories=False):
        cf = configobject
        self.meta.add("Data owner", cf.get("basic","copyright_owner") )
        self.meta.add("Operator", cf.get("basic","operator", fallback="") )
        self.meta.add("Free text", cf.get("basic","freetextline", fallback="") )
        self.meta.add("Timestamp", self.time)
        self.prefix = Path(self.time.strftime(cf.get("basic","filename_timestamp_format") ))
#        self.basepath = Path(cf.basepath)
        self.datapath = Path(cf.basepath) 
        if cf.getb("basic","create_directories") and not no_new_directiories:
            self.datapath = Path(cf.basepath) / self.prefix
            log.info(f"Creating new directory for data: {self.datapath}" )
            self.datapath.mkdir() # Create subdirectory (unlikely to exist, but TODO: verify)
    def addImage(self,  imageobject): 
        self._imagelist.append(imageobject)
    # Binary representation storage in a file using the Python Pickle protocol
#    def dumpPickle(self,  extension = ".pck"):
#        fn = self.datapath / "".join((self.prefix,extension))
#        with open(fn, "wb") as f: pickle.dump(self, f)
#    @classmethod
#    def loadPickle(cls,fn): 
#        with open(fn, "rb") as f: return pickle.load(f)  
#------------------------------------------------------------------------------------------------------    
class SampleImage(SampleBase): 
    "One image plus metadata"
    def __init__(self,  camname,  fn = None): 
        super().__init__()
        self.camname= camname
        self.meta = jkm.metadata.ImageMetadata(self.camname)  #Image-level metadata
        self.confsection= None
        self._img = None  # Full image data loaded to memory (set to None if not yet loaded)
        if fn is not None: self._fn = fn
        else: self._fn  = None
        # Record colorspace!
    @property
    def filename(self):  
        "Name of image file"
        return self._fn
    @property
    def path(self):  
        return Path(self._fn)
    def samefile(self,fn):
        "returns true is this image is a link to filename fn"
        return self.path.samefile(Path(fn))
    def unloadImageData(self): 
        self._img = None  # Delete in-memory copy of image data 
    def encodeJSON(self):
        "Return a JSON serializable representation."
        self._img = None # Do not serialise in-memory copy of image
        d = {}
        d[f"__{type(self).__name__}__"] = True
        d['cameraname'] = self.cameraname
        d['confsection'] = self.confsection
        d['_fn'] = self._fn
        d['meta'] = self.meta.encodeJSON()
        return d
    def readImage(self,filename = None, colourspace = cv2.IMREAD_COLOR,  force_reload=False): 
        """Returns image as a cv2/numpy array. 
        
        Loads data from disk if it has not already been loaded. Reloading can be forced using the force_reload flag. 
        Raises jkm.errors.FileLoadingError is datais not accessible"""
        if (self._img is not None) and (not force_reload) and (filename == None): return self._img 
        try:
            fn = filename or self._fn  # Use filename from mothod call, if any
            # HACK:
            self._fn = Path(fn)
            self._img = jkm.tools.load_img(fn)
#            self._img = cv2.imread(str(fn), colourspace)            
            return self._img
        except SystemError as msg:
            log.warning(f"Reading file {str(filename)} failed" )
            raise jkm.errors.FileLoadingError(msg)
#    def writeImage(filename): pass
    def copyMetadatafFomConf(self, configobject):
        cf = configobject
        self.addMeta("Free text", cf.get(self.confsection,"freetextline", fallback=""))
        self.addMeta("Image timing", self.time)
    def addMeta(self,title,content=""):
        self.meta.add(title,  content)
    def addlogMeta(self,title,content="",lvl=logging.INFO):
        self.meta.addlog(title,  content, lvl=lvl)
    def getsubimage(self,  rect):
        "Rect to [x1,y1,x2,y2,rot] from upper left corner"
        x1,y1,x2,y2,rot = rect
        img = self.readImage()
        return img[y1:y2, x1:x2] 
    def readbarcodes(self):
        img = self.readImage()
        bkdata = jkm.barcodes.extractbarcodedata(img,  encoding='ascii')
        return bkdata        
    def rotate(self, angle): # angle = 0,90,180,270
        print("ROTATE CALLED")
        angle = int(angle)
        if angle:
            print("ROTATING", self.name)
            img = self.readImage()
            rotcode = deg2rotcode[angle]
            self._img = cv2.rotate(img, rotateCode = rotcode)
        
#------------------------------------------------------------------------------------------------------    
class SpecimenImage(SampleImage):
    has_specimens = True
    has_labels = False
    def __init__(self,  camname,  fn = None): 
        super().__init__(camname,  fn)
#    def specimenCrop(self): pass
#------------------------------------------------------------------------------------------------------    
class LabelImage(SampleImage):
    has_specimens = False
    has_labels = True
    def __init__(self,  camname,  fn = None): 
        super().__init__(camname, fn)
        self._textareas = None
    @property
    def textareas(self):  
        "Access textareas once they have been identified using findtextareas()"
        return self._textareas
    def findtextareas(self,  method="EAST"):
        "Find areas with text using EAST text detector"
        img = self.readImage()
        if ( method.lower() == "east" ): 
            log.debug("Find areas with text using EAST text detector")
            self._textareas = jkm.ocr.find_text_rects(img)
            return self.textareas
        else:
            log.critical("Only EAST text detection is currently supported")
            self._textareas = []
        return self._textareas
    def savetextareas(self, namehdr):
        x = 1
        try:
            for rect in self._textareas:
                imgx = self.getsubimage(rect) # Get subimage            
                imgname = self.filename.stem
                fullfn = self.filename.with_name(f"{imgname}{namehdr}{x}.jpg")
                log.debug(f"Storing individual label image: {fullfn}")
                jkm.tools.save_img(fullfn,imgx)
                x += 1
        except IOError: pass
    def ocr(self, force_all_image_ocr = False): 
        # If not all_image_ocr, examine only text areas previously found
        txt = ""
        if not self._textareas or force_all_image_ocr :
            log.debug(f"OCR call for {self.camname}, full frame")
            img = self.readImage()
            txt = jkm.ocr.ocr(img)
        else:  # OCR recognised text areas one at a time
            x = 1
            for area in self._textareas:
                log.debug(f"OCR call for {self.camname}, text area {x}")
                txt += " " + jkm.ocr.ocr(self.getsubimage(area))
                x += 1
        return txt
#    def readMetadata(self): pass
#    def writeMetadata(self): pass    

class CombinedImage(SpecimenImage, LabelImage): # Note: potential problems with inheritance, resolve!
    has_specimens = True
    has_labels = True
    def __init__(self,  camname,  fn = None): 
        super().__init__(camname,  fn)

if __name__ == '__main__': #SImple testing
    si = SampleEvent()
    print(si.toJSON())
