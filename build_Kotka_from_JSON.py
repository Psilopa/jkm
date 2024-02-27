from abc import ABC
from pathlib import Path
import datetime,  logging,  os, re
#import  pickle
import cv2
import jsonpickle
import jkm.metadata
import jkm.ocr
import jkm.tools
from collections import UserDict

log = logging
dir_to_process = r"Z:\stackphotos2\2022_04_07"


class metaStorage(UserDict):
    "A dictionary-like metadata storage container (should keep order in Python 3.7+)"
    def addlog(self,title,content="",lvl=logging.INFO):
        "Add metadata and also write to logging"
        self.data[title] = content
        log.log(lvl, f"{title}: {content}" )
    def add(self,title,content=""):
        self.data[title] = content        
#    def encodeJSON(self):
#        d = {}
#        d[f"__{type(self).__name__}__"] = True
#        d.update(vars(self))
#        return d
#    def toSimpleText(self,f):
#        for k,v in self.data: f.write( f"{k}: {v}\n" )
#    def fromSimpleText(self,f):
#        newdata = []
#        for l in f.readlines(): 
#            k, v = [x.strip() for x in l.split(":", 1)]
#            newdata.append((k, v))
#        self.data  = newdata
#        
class EventMetadata(metaStorage):
    def __init__(self):
        super().__init__(self)
        
class ImageMetadata(metaStorage):
    def __init__(self, cameraname="unknown"):
        super().__init__(self) 
        self.label = cameraname    
    def addlog(self,title,content="",lvl=logging.INFO):
        "Add metadata and also write to logging"
        self.data[title] = content
        log.log(lvl, f"{self.label} - {title}: {content}" )

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
    @staticmethod
    def fromJPGfile(imgfile, conf, label="generic_camera"): # Assumes jpg file name is metadata file name
        log.debug("Creating sample data from JPEG image and config file metadata")
        itime = getFileCreationDateTime(imgfile)
        imgfile = Path(imgfile)
        image = CombinedImage(label, fn = imgfile)
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
    def __init__(self,  label,  fn = None): 
        super().__init__()
        self.label= label
        self.meta = jkm.metadata.ImageMetadata(self.label)  #Image-level metadata
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
            self._img = cv2.imread(str(fn), colourspace)       
            self._fn = Path(fn)
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
            log.debug(f"OCR call for {self.label}, full frame")
            img = self.readImage()
            txt = jkm.ocr.ocr(img)
        else:  # OCR recognised text areas one at a time
            x = 1
            for area in self._textareas:
                log.debug(f"OCR call for {self.label}, text area {x}")
                txt += " " + jkm.ocr.ocr(self.getsubimage(area))
                x += 1
        return txt
#    def readMetadata(self): pass
#    def writeMetadata(self): pass    

class CombinedImage(SpecimenImage, LabelImage): # Note: potential problems with inheritance, resolve!
    has_specimens = True
    has_labels = True
    def __init__(self,  label,  fn = None): 
        super().__init__(label,  fn)



# 1. find files

datafile_suffixes = ['.json']
datafile_patterns = ["*"+x for x in datafile_suffixes]


def find_meta_files(dirname):
    d = Path(dirname)
    print(f"Finding files to process in" , d)
    res = []
    for pat in datafile_patterns: 
        tempr = d.rglob(pat)
        tempr = [x for x in tempr if ( str(x).find("textarea") == -1 )] # Skip files with "textarea" in their name
        print("found", tempr)        
        res.extend( tempr )
    # Delete duplicate files (hard links to the same file)
#    r2 = []
#    for x in res:
#        if not path_in_list(x,r2): r2.append(x)
    return res

i2o = {
r"99°\s*31'\s*06":  ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r"99°\s*31\s*06":  ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r"18°\s*18'\s*15":  ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r"18°\s*18\s*15":  ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r' Dhiehai': ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r'Phicfiai': ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r'[PD]hi[act]hai':  ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r'Muban ': ['Thailand','Lampang','Muban Phichai',"18d18m15s","99d31m06s",'240'],
r'Phra[yv]a ':  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r'raya Cha':  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r"18°\s*17'\s*15":  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r"99°(\s*)32'(\s*)59":  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r"99°32'59":  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r"99° 32' 59":  ['Thailand','Lampang','Phraya Chae',"18d17m15s","99d32m59s",''],
r'Wat\s+Mon':  ['Thailand','Lampang','Wat Mon',"18°17´15”","99°32´59”",''],
r'Mon\s+Kao':  ['Thailand','Lampang','Mon Kao Kaew','','',''],
r'MonKao':  ['Thailand','Lampang','Mon Kao Kaew','','',''],
r'Kao\s+Kaew':  ['Thailand','Lampang','Mon Kao Kaew','','',''],
r'Farang':  ['Thailand','Lampang','Doi Farang','','',''],
r'Chae\s+Ho[mn]': ['Thailand','Lampang','Chae Hom','','',''],
r'Chas\s+Ho[mn]': ['Thailand','Lampang','Chae Hom','','',''],
r'99°\s*33': ['Thailand','Lampang','Chae Hom','','',''],
r'om\s*340M': ['Thailand','Lampang','Chae Hom','','',''],
r'Mueang':  ['Thailand','Lampang','Mueang Pan','','',''],
r' Pan ':  ['Thailand','Lampang','Mueang Pan','','',''],
r'Thung\s+Fai':  ['Thailand','Lampang','Thung Fai','','',''],
r'Patong': ['Thailand','Phuket','Patong','','',''],
r'Ban\s+Thun': ['Thailand','Chiang Mai','Ban Thun Sala','','',''],
r'Thum\s+Cala': ['Thailand','Chiang Mai','Ban Thun Sala','','',''],
r'Sala': ['Thailand','Chiang Mai','Ban Thun Sala','','',''],
r'Huay\s+Tung\s+Tao': ['Thailand','Chiang Mai','Huay Tung Tao','','',''],
r'98°\s*55': ['Thailand','Chiang Mai','Huay Tung Tao','','',''],
r'18°\s*52': ['Thailand','Chiang Mai','Huay Tung Tao','','',''],
r'Bua Tong': ['Thailand','Chiang Mai','Bua Tong','','',''],
r'Thoono ': ['Thailand','Chiang Mai','Thoeng Dang','','',''],
r'Thoaono': ['Thailand','Chiang Mai','Thoeng Dang','','',''],
r'Thoen[og]': ['Thailand','Chiang Mai','Thoeng Dang','','',''],
r'Pa Pae': ['Thailand','Chiang Mai','Pa Pae','','',''],
r'19°\s*07': ['Thailand','Chiang Mai','Pa Pae','','',''],
r'Prakan': ['Thailand','Chiang Mai','Chai Prakan, Pong Tam','','',''],
r'Pong Tam': ['Thailand','Chiang Mai','Chai Prakan, Pong Tam','','',''],
r'Chiangmai': ['Thailand','Chiang Mai','Chiangmai City, San Phy Sya','','',''],
r'San\s+Phy': ['Thailand','Chiang Mai','Chiangmai City, San Phy Sya','','',''],
r'Phy\s+Sya': ['Thailand','Chiang Mai','Chiangmai City, San Phy Sya','','',''],
r'Koh\s+Chang': ['Thailand','Trat','Koh Chang','','',''],
r'Ko\s+Khan': ['Thailand','Trat','Koh Chang','','',''],
r'attaya': ['Thailand','Chonburi','Pattaya','','',''],
r' Ubud ': ['Indonesia','Bali','Ubud','','',''],
r'Karon': ['Thailand','Phuket','Karon','','',''],
r'Phrea\s+Ee': ['Thailand','Krabi','Koh Lanta, Baam Phra Ae','','',''],
r'Kuala\s+Te': ['Malaysia','Langkawi','Kuala Temoyong','','',''],
r'Phu\s+Dua': ['Malaysia','Chiang Rai','Phu Dua','','',''],
    }


c2oPell = {
'Pellinen': ['Pellinen, Markku'],
'Pe11inen': ['Pellinen, Markku'],
'Markku': ['Pellinen, Markku'],
'llinen leg.': ['Pellinen, Markku'],
    }
defloc = ['','','','','','']
defleg = ['',]

def splitbarcode(s):
    x = s.split('/')[-1]
    if len(x) == 1: return ""
    else:
        x = s.split('/')[-1]
        return x.split('.')

i = 0
outf = open("output.csv",'w')
cid = ("","")
cids = {}
print("Ready to start")
for fn in find_meta_files(dir_to_process):
    print("found meta file", fn)
    with open(fn,"rb") as f:
        i += 1
        if i>1000: break
        outdata = []
        se = jsonpickle.decode(f.read())
        ocr = 'Combined OCR result for all images'
        idt = 'Barcode contents'
        if len(se.imagelist) < 1: continue
        if not se.imagelist[0].meta.get(idt,""): continue
        else:
            bid = splitbarcode(se.imagelist[0].meta.get(idt,"")[0])
            if len(bid) == 0: continue
            idno = bid[-1]
            if len(bid) >1: idns = bid[-0]
            else: idns = ""
        cid = (idns,idno)        
        ocr = se.meta.get(ocr,"")
        if cid in cids:
            continue
        else: cids[cid] = ""
        if not ocr: continue
        locmatch = defloc
        legmatch = defleg
        for k in i2o.keys():
            res = re.search(k,ocr)
            if res is not None: locmatch = i2o[k]
        if locmatch is defloc: print(ocr)
        for k in c2oPell.keys():
            res = re.search(k,ocr)
            if res is not None: legmatch = c2oPell[k]

        #Print result
        output = [idns,idno]
        output.extend(locmatch)
        output.extend(legmatch)
        outf.write(";".join(output))
        outf.write("\n")
#        print(";".join(output))
#        print("\n")
outf.close()
