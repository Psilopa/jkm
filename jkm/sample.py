import abc
from pathlib import Path
import datetime,  logging,  os
#import  pickle
import cv2
import jsonpickle
import jkm.metadata
import jkm.ocr
import jkm.tools
from jkm.digitisation_properties import DigipropFile
import jkm.errors

log = logging.getLogger() # Overwrite if needed
deg2rotcode = {90: cv2.ROTATE_90_CLOCKWISE,
               180: cv2.ROTATE_180,
               270: cv2.ROTATE_90_COUNTERCLOCKWISE}

# Helper functions
def _UNIQUE(s) :return list(set(s))

def getFileCreationDateTime(fn):
    # Does not work well on POSIX systems, which return the last modified date for getctime
    timestamp =  os.path.getctime(fn)
    return datetime.datetime.fromtimestamp(timestamp)

#def create_new_image(imgtype): 
#    "Create a new SampleImage subclass instance based on the requested type"
#    if imgtype.lower().strip() == 'label': return LabelImage()
#    if imgtype.lower().strip() == 'specimen': return SpecimenImage()
#------------------------------------------------------------------------------------------------------    
class SampleBase(abc.ABC):
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
class SampleEvent(SampleBase,  abc.ABC):
    "Container for 0+ photos of an sample and event-level metadata."
    def __init__(self,  time = None):
        super().__init__(time)
        self._imagelist = [] # List of SamplePhoto subclass instances
        self.prefix  = "" # Common file name prefix (often/ALWAYS same as self.datapath?)
        self.datapath = "" # Data directory for this record 
        self.meta = jkm.metadata.EventMetadata() # Event-level metadata
#        self._has_metadatafile = False
#        self._is_directory = False
        self._identifier = None
        self._shortidentifier = None
    @property
    def identifier(self):  return self._identifier
    @identifier.setter
    def identifier(self, x):  
        self._identifier = x    
        self._shortidentifier = self._shortenidentifier(x)
    @property
    def shortidentifier(self):  return self._shortidentifier
    @property
    def is_directory(self):  return self._is_directory
    @property
    def feature_metadata(self):  return self._has_metadatafile
    @property
    def imagelist(self, labels=[]):  
        if not labels: 
            return self._imagelist
        else: 
            #Only return images with certain labels
            return [x for x in self._imagelist if x.label in labels] 
#    @property
#    def filelist(self):
#        # INCOMPLETE IMPLEMENTATION, ONLY IMAGE FILES
#        filelist = [Path(x.filename) for x in self._imagelist]
#        return tuple(filelist) 
    @abc.abstractmethod
    def _shortenidentifier(self, x): 
        return x
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
    def rename_all_files(self, prefix,  prefix_separator= "_"):
        """Rename source file"""
        if not self.identifier: raise jkm.errors.JKError("No known sample identifier, cannot rename files")
        for image in self.imagelist:
            try: 
                log.debug(f"Renaming files based on barcode content: prefix {prefix}, oldname {image.path}")
                newpath = image.path # Default new name = old name
                new_filename = prefix + prefix_separator + image.path.name
                newpath= image.path.parent / Path(new_filename)
                log.debug(f"New name for {image.path} is {newpath}")            
                image.rename(newpath)
            except PermissionError as msg:
                log.warning("Renaming file failed with error message: %s" % msg)
            except FileExistsError as msg:
                log.warning("Target file name already exists, skipping: %s" % msg)
#------------------------------------------------------------------------------------------------------    
class SampleImage(SampleBase): 
    "One image plus metadata"
    def __init__(self,  label,  fn = None): 
        super().__init__()
        self.label= label
        self.meta = jkm.metadata.ImageMetadata(self.label)  #Image-level metadata
        self.confsection= None
        self._img = None  # Full image data loaded to memory (set to None if not yet loaded)
        self._fn = fn
        # Record colorspace!
    @property
    def filename(self):  return self._fn
    @property
    def path(self):  # Note: fails is _self._fn is still set to None
        return Path(self._fn)
    def samefile(self,fn):
        "returns true is this image is a link to filename fn"
        return self.path.samefile(Path(fn))
    def rename(self,newpath):
        "Rename the corresponding file on the file system"
        #TODO: needs error state handling and documentation
        self.path.rename(newpath)
        self._fn = newpath
    def unloadImageData(self): 
        self._img = None  # Delete in-memory copy of image data 
    def encodeJSON(self):
        "Return a JSON serializable representation."
        self._img = None # Do not serialise in-memory copy of image
        d = {}
        d[f"__{type(self).__name__}__"] = True
        d['label'] = self.label
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
    def readbarcodes(self, qrpackage):
        img = self.readImage()
        bkdata = jkm.barcodes.extractbarcodedata(img, qrpackage, encoding='ascii')
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
    def __init__(self,  label,  fn = None): 
        super().__init__(label,  fn)
#    def specimenCrop(self): pass
#------------------------------------------------------------------------------------------------------    
class LabelImage(SampleImage):
    has_specimens = False
    has_labels = True
    def __init__(self,  label,  fn = None): 
        super().__init__(label, fn)
        self._textareas = None
    @property
    def textareas(self):  
        "Access textareas once they have been identified using findtextareas()"
        return self._textareas
    def findtextareas(self,  nnfn):
        "Find areas with text using EAST text detector"
        img = self.readImage()
        log.debug("Find areas with text using EAST text detector")
        self._textareas = jkm.ocr.find_text_rects(img,nnfn)
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
    def ocr(self, ocrcommand, force_all_image_ocr = False): 
        # If not all_image_ocr, examine only text areas previously found
        txt = ""
        if not self._textareas or force_all_image_ocr:
            log.debug(f"OCR call for {self.label}, full frame")
            img = self.readImage()
            txt = jkm.ocr.ocr(img,ocrcommand)
        else:  # OCR recognised text areas one at a time
            x = 1
            for area in self._textareas:
                log.debug(f"OCR call for {self.label}, text area {x}")
                txt += " " + jkm.ocr.ocr(self.getsubimage(area),ocrcommand)
                x += 1
        return txt
#    def readMetadata(self): pass
#    def writeMetadata(self): pass    

class CombinedImage(SpecimenImage, LabelImage): # Note: potential problems with inheritance, resolve!
    has_specimens = True
    has_labels = True
    def __init__(self,  label,  fn = None): 
        super().__init__(label,  fn)

#------------------------------------------------------------------------------------------------------    
class LuomusLineSample(SampleEvent): 
    allowed_URI_domains = ["http://tun.fi/", "http://id.luomus.fi/",""]
    def __init__(self,  time=None):
        super().__init__(time)
#        self._has_metadatafile = True
#        self._is_directory = True
        self.digipropfile = DigipropFile() 
    def _grab_identifier_prefix(self, ident): # everything up to the last /
        if not "/" in ident:
            return None
        else:
            parts = ident.split("/")
            noend = "/".join(parts[:-1]) + "/"
            return noend        
    def verify_identifier(self):  # Check if thosed identifier is a valid Luomus identifier
        # SIMPLISTIC IMPLEMENTATION
        pref = self._grab_identifier_prefix(self.identifier)
        if pref is None: return True  # No URI to test
        for uriok in self.allowed_URI_domains:
            if uriok in self.identifier: return True
        return False # No matching URI pattern found    
    def _shortenidentifier(self, x): # Overrides base class
        separator = r'/'
        return x.split(separator)[-1] 
    def original_timestamp(self): #helper function for insect line processing
        marker = "dc1."
        x = str(self.datapath.name).split(marker) # Look for marker in last element of directory name
        if len(x) != 2: return ""
        else: return x[-1] # Last element
    def rename_directories(self, config,prefix,ignore_domain=True):
        """Rename files/dirs if sample ID data is available (from QR code parsing or other source)

        id0: a single (long or short)
        ignore_domain = if True, only the namespace.number part is used 
        Renaming details are provided in the config class instance passed as an argument

        On failure, can return at least:
        - PermissionError
        - FileExistsError
        """        
        # TODO: EXTEND TO POSSIBLE SUBDIRECTORIES?
        newpath = self.datapath # Default to no change
        basepath = self.datapath.parent
        if ignore_domain: id0 = self.shortidentifier
        else: id0 = self.identifier
        if not id0: raise jkm.errors.JKError("No identifier known, cannot rename directory")
        newprefix = "_".join([id0 , prefix])            
        if config.getb("basic","create_directories"): # if a subdirectory was created for data
             newbase = basepath / id0 # example [basebath]/GX.38276
             newpath = newbase / newprefix # example [basebath]/GX.38276/GX.38276_timestamp
             if not newbase.exists(): newbase.mkdir() 
        else:
             newpath = basepath / newprefix 
        log.debug(f"Renaming {self.datapath} to {newpath}")        
        self.datapath.rename(newpath) 
        self.datapath= newpath # Set datapath to the new value only if everything preceding was successful
#------------------------------------------------------------------------------------------------------    
class LuomusPlantLineSample(LuomusLineSample): 
    def __init__(self,  time=None):
        super().__init__(time)
    @staticmethod    
    def from_directory(dirpath, conf): 
        """Create a Sample object from a directory path with files like those created by the Luomus Plant Imaging Line.
    
arguments: 
    dirpath = a Path instance pointing to the directory containing the data files
    conf = a JKM configuration data instance
"""
        # Most code shared with MZHInsectLineSample!
        log.debug("Creating sample data from JPEG image and jkm config file metadata") 
        # Does not currently read digitization.propersies or the XML file
        filepath = dirpath / Path(conf.get("sampleformat", "label_file"))
        # Extract creating time from JPG and use it as the Sample event time        
        itime = getFileCreationDateTime(filepath)
        s = LuomusLineSample( time = itime )
        s.copyMetadatafFomConf(conf, no_new_directiories=True)
        s.datapath = dirpath
        s.name = f"{dirpath.name}"        
        s.prefix = dirpath
        # Load image (just one on plant line)
        title = conf.get("sampleformat", "label_title")
        image = CombinedImage(title, fn = filepath)
        s.addImage(image)
        return s           
#------------------------------------------------------------------------------------------------------            
class LuomusInsectLineSample(LuomusLineSample): 
    def __init__(self,  time=None):
        super().__init__(time)
    @staticmethod
    def from_directory(dirpath, conf): 
        log.debug("Creating sample data from JPEG image and jkm config file metadata") 
        # Does not currently read digitization.propersies or the XML file
        labelpath = dirpath / Path(conf.get("sampleformat", "label_file"))
        # Extract creating time from JPG and use it as the Sample event time        
        itime = getFileCreationDateTime(labelpath)
        s = LuomusLineSample( time = itime )
        s.copyMetadatafFomConf(conf,  no_new_directiories=True)
        s.datapath = dirpath
        s.name = f"{dirpath.name}"        
        s.prefix = dirpath
        #Load label image
        label_label = conf.get("sampleformat", "label_title")
        labelimage = LabelImage(label_label, fn = labelpath)
        s.addImage(labelimage)
        #Load object (insect/plant) images
        objectfiles = conf.getlist("sampleformat", "object_files")
        object_titles = conf.getlist("sampleformat", "object_titles")
        objectfilepaths= [dirpath / Path(x) for x in objectfiles]
        for ofp, ofn in zip(objectfilepaths, object_titles):
            s.addImage( SpecimenImage(ofn, fn = ofp)  )
        return s             
#------------------------------------------------------------------------------------------------------    
class SingleImageSample(SampleEvent): 
    """A single image based minimal sample event"""
    def __init__(self,  time = None):
#        self._has_metadatafile = False
#        self._is_directory = False
        super().__init__(time)
    @staticmethod
    def from_image_file(imgfile, conf, label="generic_camera"): 
        # Assumes jpg file name is metadata file name
        log.debug("Creating sample data from JPEG image and config file metadata")
        itime = getFileCreationDateTime(imgfile)
        imgfile = Path(imgfile)
        image = CombinedImage(label, fn = imgfile)
        # Extract creating time from JPG and use it as the Sample event time        
        s = SingleImageSample( time = itime )
        s.copyMetadatafFomConf(conf,  no_new_directiories=True)
        s.datapath = imgfile.parent
        s.addImage(image)
        s.prefix = imgfile.stem
        return s        
    def _shortenidentifier(self, x): # Overrides base class
        separator = r'/'
        return x.split(separator)[-1] # Last element
#------------------------------------------------------------------------------------------------------    

#if __name__ == '__main__': #SImple testing
#    si = SampleEvent()
#    print(si.toJSON())
