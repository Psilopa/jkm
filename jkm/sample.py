import abc, re
from pathlib import Path
from datetime import datetime
import logging,  os, validators
#import  pickle
import cv2
import jsonpickle
import jkm.samplemetadata, jkm.ocr, jkm.tools, jkm.errors
from jkm.digitisation_properties import DigipropFile
import numpy as np
#from urllib.request import urlopen
from urllib.parse import urlparse, urlunparse

# For typing
from jkm.typing import *

log = logging.getLogger() # Overwrite from calling script for fancier logging
deg2rotcode = {90: cv2.ROTATE_90_CLOCKWISE,
               180: cv2.ROTATE_180,
               270: cv2.ROTATE_90_COUNTERCLOCKWISE}

def getFileCreationDateTime(fn:str|Path) -> datetime:
    # Does not work well on POSIX systems, which return the last modified date for getctime
    timestamp =  os.path.getctime(str(fn))
    return datetime.fromtimestamp(timestamp)

class Results():  # Partial overlap with metadata ... think about this later
    """Sample analysis results."""
    ocrtext = None
    labeltext_ai1 = None
    barcodes = None
#------------------------------------------------------------------------------------------------------    
class SampleBase(abc.ABC):
    supports_rename_files = False
    supports_rename_directories = False    
    def __init__(self, time:datetime|None = None): 
        if time is None: self._time = datetime.now()
        else: self._time = time
        self.name = str(self) # TODO: replace with better names in subclasses, should use timestamp or camera name
    @property
    def time(self:Self) -> datetime:  return self._time
    def encodeJSON(self:Self) -> None|dict[str,Any]:
        jsonpickle.set_preferred_backend('json')
        jsonpickle.set_encoder_options("json", ensure_ascii=False,  indent=2)        
        return jsonpickle.encode(self)
    @staticmethod
    def fromJSONfile(fpath:Path) -> Any|None:
        with fpath.open() as f:
            return jsonpickle.decode(f.read())

#------------------------------------------------------------------------------------------------------
class SampleEvent(SampleBase,  abc.ABC):
    "Container for 0+ photos of an sample and event-level metadata."
    def __init__(self,  time: datetime|None = None):
        super().__init__(time)
        self._imagelist:list[SampleImageBase] = [] # List of SampleImage subclass instances
        self.prefix: str|Path = "" # Common file name prefix (often/ALWAYS same as self.datapath?)
        self.datapath: Path = Path() # SHOULD THIS BE None?
        self.meta = jkm.samplemetadata.EventMetadata() # Event-level metadata
        self._identifier: str|None = None
        self._shortidentifier: str|None = None
        self.results = Results()
    @property
    def identifier(self:Self) -> str|None:  return self._identifier
    @identifier.setter
    def identifier(self, x: str):  
        self._identifier = x    
        self._shortidentifier = self._shortenidentifier()# Accessed self._identifier
        self.name = x
    @property
    def shortidentifier(self:Self) -> str|None:  return self._shortidentifier
    @property 
    def imagelist(self, labels:list[str]=[]) -> tuple(SampleImageBase,...):  
        if not labels: 
            return tuple(x for x in self._imagelist)
        else: 
            #Only return images with certain labels
            return tuple(x for x in self._imagelist if x.label in labels)
#    @property
#    def filelist(self:Self):
#        # INCOMPLETE IMPLEMENTATION, ONLY IMAGE FILES
#        filelist = [Path(x.filename) for x in self._imagelist]
#        return tuple(filelist) 
    def _shortenidentifier(self) -> str:
        """Shorten a given identifier string for display and file renaming purposes.

        The default implementation does nothing."""
        return x
    def verify_identifier(self:Self) -> bool:
        """Check if identifier is a valid one. Default imprementation accepts anything.

        Reimplement in child classes if you want validation."""
        return True
    def writeMetaJSON(self,  extension:str = ".json") -> None: 
        "Save SampleEvent metadata to a file"
        for img in self._imagelist: img.unloadImageData()
        metafn = self.datapath / "".join( (str(self.prefix),extension) )
        log.info(f"Writing metadata to file {metafn}")
        with metafn.open("w",encoding="utf8") as metaf:
            metaf.write(str(self.encodeJSON()))
#    def copyMetadatafFomConf(self, configobject, no_new_directiories:bool=False) -> None:
#        cf = configobject
#        self.meta.add("Data owner", cf.get("meta","copyright_owner") )
#        self.meta.add("Operator", cf.get("meta","operator") )
#        self.meta.add("Free text", cf.get("meta","textline") )
#        self.meta.add("Timestamp", self.time)
#        self.prefix = Path(self.time.strftime(cf.get("postprocessor","filename_timestamp_format") ))
#        self.basepath = Path(cf.basepath)
#        self.datapath = Path(cf.basepath) 
##        if cf.getb("task","create_directories") and not no_new_directiories:
#            self.datapath = Path(cf.basepath) / self.prefix
#            log.info(f"Creating new directory for data: {self.datapath}" )
#            self.datapath.mkdir() # Create subdirectory (unlikely to exist, but TODO: verify)
    def addImage(self,  imageobject) -> None: 
        self._imagelist.append(imageobject)
    # Binary representation storage in a file using the Python Pickle protocol
#    def dumpPickle(self,  extension = ".pck"):
#        fn = self.datapath / "".join((self.prefix,extension))
#        with open(fn, "wb") as f: pickle.dump(self, f)
#    @classmethod
#    def loadPickle(cls,fn): 
#        with open(fn, "rb") as f: return pickle.load(f)  
    def rename_all_files(self, prefix:str,  prefix_separator:str= "_") -> None:
        """Rename sample file(s).

        NOTE: Currently only renames *image* files."""
        if not self.identifier: raise jkm.errors.JKError("No known sample identifier, cannot rename files")
        for image in self.imagelist:
            try: 
                log.debug(f"Renaming files based on barcode content: prefix {prefix}, oldname {image.path}")
                oldpath = image.path
                newpath = oldpath # Default new name = old name
                filename = prefix + prefix_separator + oldpath.name
                newpath = image.path.parent / filename
                log.debug(f"New name for {image.path} is {newpath}")
                if newpath != oldpath:
                    image.rename(newpath)
            except PermissionError as msg:
                log.warning("Renaming file failed with error message: %s" % msg)
            except FileExistsError as msg:
                log.warning("Target file name already exists, skipping: %s" % msg)
    def write_postprocessor_report(self, conf, properties_filename:str|Path|None = None):
        # By default, do nothing
        return # 
    @staticmethod
    # Override in child classes if needed!
    def find_samples(dirname: str|Path,
                     datafile_patterns: list[str]
                     ) -> tuple[type_url]:
        """Returns a list of urls pointing to a source that can be used to build an Sample. Child classes can replace this.

        Arguments:
##        dirname - string or Path: path to the direcotry holding items

        Keywords:
        datafile_patterns - string: glob pattern for recognizing the file(s)
        """
        
        log.debug(f"Finding '{datafile_patterns}' files to process in {dirname}" )
        d = Path(dirname) 
        result = []
        for pat in datafile_patterns:
            filepaths = d.rglob(pat)
            log.debug(f"Looking for pattern {pat} in {dirname}")
            filepaths = [jkm.tools.path2url(x) for x in filepaths if ( str(x).find("textarea") == -1 )] # Skip files with "textarea" in their name
            result.extend( filepaths )
        # Delete duplicate files (hard links to the same file)        
        return jkm.tools.unique(result)
    def rename_directories(self, config, prefix:str, ignore_domain:bool =True) -> None:
        raise jkm.errors.JKError("Trying to rename directories in an object that does not support it.")
#-----------------------------IMAGE CONTAINERS---------------------------------------------------------------    
class SampleImageBase(SampleBase,  abc.ABC): 
    "One image plus metadata"
    #Class properties
    supports_rename_directories = False    
    has_specimens = False # Property
    has_labels = False # Property
    def __init__(self,  label:str,  url:type_url, time: datetime|None= None):
        super().__init__(time)
        log.debug(f"Creating {type(self).__name__} from URL {url}.")
        self._bitmap:type_image|None = None  # Full image data loaded to memory (set to None if not yet loaded)
        self._loaded:bool = False
        self.url:type_url = url # Also sets self._parsed_url
        self.name:str = f"{type(self).__name__} ({url})" # For images, the image source is a good name
        self.label:str = label
        self.meta = jkm.samplemetadata.ImageMetadata(self.label)  #Image-level metadata
        self.confsection:dict|None = None
        
        # Data about the actual image: can we surrpot renaming
        if self._parsed_url.scheme in ("file",):
            self.supports_rename_files:bool = True # We can rename local resources
    # abstract function
    @abc.abstractmethod
    def _loadImage(self, colourspace:int = cv2.IMREAD_COLOR) -> None: return
    # properties
    @property
    def url(self:Self) -> type_url: return self._url
    @url.setter
    def url(self, value:type_url):
        self._url = value
        self._parsed_url = urlparse(self.url)
    @property
    def bitmap(self:Self) -> type_image|None:
        # TODO: Try to load if unloaded!
#        assert self._bitmap, "Trying to access bitmap data before loading it."
        return self._bitmap
    @bitmap.setter
    def bitmap(self, newbitmap:type_image|None) -> None:
        self._bitmap = newbitmap
        if self._bitmap is None: self._loaded = False # Set to None
        else: self._loaded = True        
    @property
    def path(self:Self) -> Path:
        assert self._parsed_url.scheme == "file" # Should be accessed only for files
        return Path(self._parsed_url.path)
    # Functions
    def encodeJSON(self:Self) -> dict:
        "Return a JSON serializable representation."
        # TODO: ADD FULL STRUCTURE HERE
        # TODO: IMPLEMENT IN CHILD CLASSES
        d:dict = {str:str}
        d[f"__{type(self).__name__}__"] = True
        d['label'] = self.label
        d['confsection'] = str(self.confsection)
        d['_url'] = self.url
        d['meta'] = self.meta.encodeJSON()
        return d
    def unloadImageData(self:Self) -> None: 
        self.bitmap = None  # Delete in-memory copy of image data
#    def copyMetadatafFomConf(self, configobject) -> None:
#        cf = configobject
#        self.addMeta("Free text", cf.get(self.confsection,"freetextline", fallback=""))
        self.addMeta("Image timing", self.time)
    def addMeta(self,title:str,content="") -> None:
        self.meta.add(title,  content)
    def addlogMeta(self,title:str,content:str="",lvl:int=logging.INFO) -> None:
        self.meta.addlog(title,  content, lvl=lvl)
    def getsubimage(self,  rect=tuple[int]|list[int]) -> type_image|None:
        "Rect to [x1,y1,x2,y2,rot] from upper left corner"
        x1,y1,x2,y2,rot = rect
        self._loadImage()
        if self.bitmap: return self.bitmap[y1:y2, x1:x2]
        else: return None # Nothing to rotate
    def readbarcodes(self, qrpackage) -> list[str]:
        self._loadImage()
        bkdata = jkm.barcodes.extractbarcodedata(self.bitmap, qrpackage, encoding='ascii')
        return bkdata        
    def rotate(self, angle: int) -> None: # angle = 0,90,180,270
        angle = int(angle)
        if angle:
            self._loadImage()
            rotcode = deg2rotcode[angle]
            if self.bitmap: self.bitmap = cv2.rotate(self.bitmap, rotateCode = rotcode)        
    def rename(self,newpath: Path) -> None:
        """Rename the corresponding file on the file system.

        Raises a jkm.errors.FileLoadingError if called for non-local file resources.
        """
        if not self.supports_rename_files:
            raise jkm.errors.FileLoadingError("Cannot rename resources that are not local.")
        # Create new URL from the old one, replacing the file path
        comps = urlparse(self.url)
        comps._replace( path=str(newpath) )
        self.path.rename(newpath)
        self.url = urlunparse(comps) # Also resets self._parsed_url

class SampleImage(SampleImageBase): 
    "One image plus metadata"
    def __init__(self,  label:str,  url:type_url,  time:datetime|None = None): 
        super().__init__(label, url,  time)
    def _loadImage(self, colourspace:int = cv2.IMREAD_COLOR) -> None: 
        """Returns image as a cv2/numpy array. 
        
        Loads data from disk if it has not already been loaded. Reloading can be forced using the force_reload flag. 
        Raises jkm.errors.FileLoadingError is datais not accessible"""
        if (self.bitmap is not None): return # We are already set
        try:
            if self.url is not None:
                self.bitmap = jkm.tools.load_img(self.url)
            else: raise jkm.errors.FileLoadingError(f"No file URL set.") 
        except SystemError as msg:
            log.warning(f"Reading file {str(self.url)} failed" )
            self.bitmap = None # Reset after failure just in case
            raise jkm.errors.FileLoadingError(msg)        
#    def writeImage(filename): pass

class SpecimenImage(SampleImage):
    #Class properties
    has_specimens = True # Property
    has_labels = False # Property
    def __init__(self,  label:str,  url:type_url,  time:datetime|None = None) :
        super().__init__(label,  url,  time)

class LabelImage(SampleImage):
        #Class properties
    has_specimens = False # Property
    has_labels = True # Property
    def __init__(self,  label:str,  url:type_url,  time:datetime|None = None) :
        super().__init__(label,  url,  time)
        self._textareas = []
    @property
    def textareas(self:Self) -> list:  
        "Access textareas once they have been identified using findtextareas()"
        return self._textareas
    def findtextareas(self,  nnfn:str) -> Collection[type_rotated_rect]:
        "Find areas with text using EAST text detector"
        img = self._loadImage()
        log.debug("Find areas with text using EAST text detector")
        return jkm.ocr.find_text_rects(img,nnfn)
    def savetextareas(self, namehdr:str) -> None:
        x = 1
        try:
            for rect in self._textareas:
                imgx:type_image|None = self.getsubimage(rect) # Get subimage            
                imgname = self.path.stem
                fullfn = self.path.with_name(f"{imgname}{namehdr}{x}.jpg")
                log.debug(f"Storing individual label image: {fullfn}")
                if imgx: jkm.tools.save_img(fullfn,imgx)
                x += 1
        except IOError: pass
    def ocr(self, ocrcommand:str, force_all_image_ocr:bool = False) -> str: 
        # If not all_image_ocr, examine only text areas previously found
        txt = ""
        if not self._textareas or force_all_image_ocr:
            log.debug(f"OCR call for {self.label}, full frame")
            img = self._loadImage()
            txt = jkm.ocr.ocr(img,ocrcommand)
        else:  # OCR recognised text areas one at a time
            x = 1
            for area in self._textareas:
                log.debug(f"OCR call for {self.label}, text area {x}")
                txt += " " + jkm.ocr.ocr(self.getsubimage(area),ocrcommand)
                x += 1
        return txt
#    def readMetadata(self:Self): pass
#    def writeMetadata(self:Self): pass    

class CombinedImage(SpecimenImage, LabelImage): 
    def __init__(self,  label:str,  url:type_url,  time:datetime|None = None) :
        # Note: potential problems with inheritance, resolve!
        super().__init__(label,  url,  time)
        # Set these after constructors to make sure we get them right
        self.has_specimens = True # Property
        self.has_labels = True # Property
#------------------------------------------------------------------------------------------------------    
class CETAFSample(SampleEvent):
    """CETAFSample extends with basic SampleEvent with CETAF identifcation validators."""
    # TODO: HARDCODED ALLOWED VALUES -> conf
    allowed_scheme = ("http",)
    allowed_domains = ("id.luomus.fi", "tun.fi")
    allowed_shortid_re = (re.compile(""),) 
    def verify_identifier(self:Self) -> bool:
        """Check of the validator value stored in a valid CETAF identifier."""
        if not self.identifier: return False # An empty id is not valid
        urlparts = urlparse(self.identifier)
        if urlparts.scheme not in self.allowed_scheme: return False
        if urlparts.netloc not in self.allowed_domains: return False
        for regrule in self.allowed_shortid_re:
            pass
        return True        
    def _shortenidentifier(self:Self) -> str: # Overrides base class
        """Shorten a given identifier string for display and file renaming purposes."""
        separator = r'/'
        return self._identifier.split(separator)[-1] # Last element

# NOTE: THIS DEFINES ORGANIZATION-SPECIFIC THINGS (FOR NOW, IDENTIFIER FORMATTING IS HERE)
MySampleBase = CETAFSample

#---------------------------------------------------------------------------------------------------    
class SingleImageSample(MySampleBase): 
    """A single image based minimal sample event"""
    supports_rename_files = True    
    supports_rename_directories = False    
    def __init__(self,  time:datetime|None = None) :
        super().__init__(time)
    @staticmethod
    def from_url(url:type_url, conf, label:str="generic_camera")-> SingleImageSample: 
        # Assumes jpg file name is metadata file name
        log.debug("Creating sample data from JPEG image and config file metadata")
        # Extract creating time from JPG and to be used as the Sample event creationtime
	# Create a CombinedImage to hold image data 
        image = CombinedImage(label, url)
        try:
            imgpath = jkm.tools.url2path( url )
            filecreated = getFileCreationDateTime(imgpath)
        except ValueError: # THis is not a local file URI
            imgpath = None
            filecreated = datetime.now()
	# Create a new SingleImageSample instance and return it 
        s = SingleImageSample( time = filecreated )
        s.name = f"{type(s).__name__} ({url})" # For images, the image source is a good name
#        s.copyMetadatafFomConf(conf,  no_new_directiories=True)
        if imgpath: # These make sense only to local files
            s.datapath = imgpath.parent # Use the directory holding the file as the Sample 'home'
            s.prefix = imgpath.stem # default naming scheme for sample-related objects
        s.addImage(image)
        return s        
#------------------------------------------------------------------------------------------------------    
class DirectorySample(MySampleBase): 
    supports_rename_files = True    
    supports_rename_directories = True    
    def __init__(self:Self,  time:datetime|None=None) :
        super().__init__(time)
        self.digipropfile = DigipropFile() 
    @staticmethod
    def _createsample(url:type_url,SampleClass):
        triggerfile = jkm.tools.url2path( url )
        # First, url is the trigger file, not the directory!
        dirpath = triggerfile.parent
        # Extract creating time from directory name 
        itime = getFileCreationDateTime(dirpath)
        s = SampleClass( time = itime )
        s.name = f"{type(s).__name__} ({dirpath})" # Set name to class(directory)
        s.datapath = dirpath
        s.prefix = dirpath
        return s
    @staticmethod
    def _createimages(datapath:Path, patterns:list[str], ImageClass) -> list[SampleImage]:
        imagefilepaths = []
        for pattern in patterns:
            foundpaths = [Path(x) for x in datapath.glob(pattern)]
            imagefilepaths.extend( foundpaths)
        imagefileurls = [jkm.tools.path2url(path) for path in imagefilepaths]
        # TODO: get object descriptions from config (already there, but unused)
        object_descriptions = [f"Image file {url}" for url in imagefileurls]
        # We do not know if these are sample or label images
        imagelist = []
        for fileurl, filename in zip(imagefileurls, object_descriptions):
            img = CombinedImage(filename, fileurl)
            imagelist.append(img)
        return imagelist       
    @staticmethod
    def from_directory(url:type_url, conf:type_conf) -> DirectorySample:
        """Directory URL (file:///...) to sample object."""
        s = DirectorySample._createsample(url, DirectorySample)
#        s.copyMetadatafFomConf(conf,  no_new_directiories=True)
        # Load all images found, treating them as combined label/specimen images
        imgsearchpatterns = conf.getlist("data","image_name_pattern")
        imagelist = DirectorySample._createimages( s.datapath,
                                                    imgsearchpatterns,
                                                    CombinedImage ) 
        for img in imagelist: s.addImage(img)
        log.debug(f"Created a DirectorySample with {len(s.imagelist)} images.")
        return s             
    def original_timestamp(self:Self) -> str: #helper function for insect line processing
        marker = "dc1."
        x = str(self.datapath.name).split(marker) # Look for marker in last element of directory name
        if len(x) != 2: return ""
        else: return x[-1] # Last element
    def rename_directories(self:Self, config:type_conf, prefix:str, ignore_domain:bool=True) -> None:
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
        if config.getb("task","create_directories"): # if a subdirectory was created for data
             newbase = basepath / id0 # example [basebath]/GX.38276
             newpath = newbase / newprefix # example [basebath]/GX.38276/GX.38276_timestamp
             if not newbase.exists(): newbase.mkdir() 
        else:
             newpath = basepath / newprefix 
        log.debug(f"Renaming {self.datapath} to {newpath}")        
        self.datapath.rename(newpath) 
        self.datapath= newpath # Set datapath to the new value only if everything preceding was successful
    def write_postprocessor_report(self, conf, properties_filename = None) -> None:
        """Write postprocessor.properties file. Uses the same format as the Luomus degitizing line .properties file"""
        if (properties_filename is None) or (not properties_filename):
            properties_filename  = Path(r"postprocessor.properties")
        else: properties_filename = Path(properties_filename) # Make sure this is a path 
        try:
            self.digipropfile.setheader( f"# {datetime.now()}" )
            self.digipropfile.update("full_barcode_data",self.identifier or "")
            self.digipropfile.update("identifier",self.shortidentifier  or "")
            self.digipropfile.update("timestamp",self.original_timestamp())
            if self.identifier: # Only one identifier-containing barcode was found
                id_OK = self.verify_identifier() # This should probably be done way earlier elsewhere
                if not id_OK: 
                    log.critical(f"{self.name}: MALFORMED IDENTIFIER {self.identifier}")
                self.digipropfile.update("url_format_OK", str(id_OK) )
            self.digipropfile.update("Q-sharp", "" )
            self.digipropfile.update("Q-color", "" )
            self.digipropfile.save( self.datapath / properties_filename )
        except OSError as msg:
            assert(properties_filename) # Should exist if this exception was triggered
            log.warning( f"Saving a properties file failed with error message: {msg}" )


class LuomusPlantLineSample(DirectorySample): 
# Inherits the specific rename function. Might want to reimplement it here more generally
    def __init__(self,  time:datetime|None=None):
        super().__init__(time)
    @staticmethod    
    def from_directory(url: type_url, conf:type_conf) -> LuomusPlantLineSample: 
        """Directory URL (file:///...) to sample object."""
        # Slightly modified version of the parent one
        s = LuomusPlantLineSample._createsample(url, LuomusPlantLineSample)
        # s.copyMetadatafFomConf(conf, no_new_directiories=True)
        # Load image (just one on plant line) TODO: Logic here is not very ideal
        title = conf.get("data", "label_title")
        filepath = s.datapath / Path(conf.get("data", "label_file"))
        image = CombinedImage(title, jkm.tools.path2url(filepath))
        s.addImage(image)
        log.debug(f"Created a LuomusPlantLineSample with {len(s.imagelist)} images.")
        return s           
#------------------------------------------------------------------------------------------------------            
class LuomusInsectLineSample(DirectorySample): 
    def __init__(self,  time:datetime|None=None):
        super().__init__(time)
    @staticmethod
    def from_directory(url:type_url, conf:type_conf) -> LuomusInsectLineSample: 
        # Slightly modified version of the parent one
        s = LuomusInsectLineSample._createsample(url, LuomusInsectLineSample)
#        s.copyMetadatafFomConf(conf, no_new_directiories=True)
        # Load image (two+ on the insect line) TODO: Logic here is not very ideal
        # Load label image
        title = conf.get("data", "label_title")
        filepath = s.datapath / Path(conf.get("data", "label_file"))
        image = LabelImage(title, jkm.tools.path2url(filepath))
        s.addImage(image)        
        # Load specimen images
        imagelist = DirectorySample._createimages( s.datapath,
                                                   conf.getlist("data","object_files"),
                                                   SpecimenImage ) 
        for img in imagelist: s.addImage(img)
        log.debug(f"Created a LuomusInsectLineSample with {len(s.imagelist)} images.")
        return s           

#------------------------------------------------------------------------------------------------------    
class FileRowSample(SingleImageSample): 
    def __init__(self,  time:datetime|None = None):
        super().__init__(time)
    @staticmethod
    def find_samples(dirname: str|Path,
                     datafile_patterns: list[str]
                     ) -> tuple[type_url]:
        """Returns a list of urls pointing to a source that can be used to build an Sample. Child classes can replace this.

        Arguments of the default version:
        dirname - directory of the target file(s)
        datafile_patterns - file name glob patterns
        """
        # While testing
        assert len(datafile_patterns) == 1
        filepath = Path(dirname) / datafile_patterns[0]
        log.debug(f"Reading '{filepath}' to find resources")
        try:
            result = []
            with filepath.open("r") as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                # Skip empty and comment lines
                if not line or line[0] == '#': continue                
                # Check line format: could be URL's or file paths
                linepath = Path(line.strip())
                if linepath.exists(): line = jkm.tools.path2url(linepath) # This is a path to an existing local file
                elif validators.url(line): pass # Should be a valid URL as-is
                else:
                    raise jkm.errors.FileLoadingError(f"Could not recognize the format of line {line} in {filepath}.")
                result.append( line.strip() )
            # Delete duplicate files (hard links to the same file)
            return jkm.tools.unique(result)
        except IOError as msg:
            raise jkm.errors.FileLoadingError(msg)
        # return the image
        return image
    @staticmethod
    def from_url(url:type_url, conf, label:str="generic_camera") -> SingleImageSample:  
        return SingleImageSample.from_url(url, conf, label="generic_camera")
#------------------------------------------------------------------------------------------------------    
