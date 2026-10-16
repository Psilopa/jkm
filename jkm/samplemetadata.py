#from pathlib import Path
import logging
from collections import UserDict

log = logging.getLogger() # Overwrite if needed

class metaStorage(UserDict):
    "A dictionary-like metadata storage container (should keep order in Python 3.7+)"
    def addlog(self,title,content="",lvl=logging.INFO, log_add_hdr = ""):
        "Add metadata and also write to logging"
        self.data[title] = content
        if not log_add_hdr:  log.log(lvl, f"{title}: {content}" )
        else: log.log(lvl, f"{log_add_hdr}- {title}: {content}" )
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
    def addlog(self,title,content="",lvl=logging.INFO, log_add_hdr = ""):
        "Add metadata and also write to logging"
        self.data[title] = content
        if not log_add_hdr:  log.log(lvl, f"{self.label} - {title}: {content}" )
        else:  log.log(lvl, f"{log_add_hdr}- {self.label} - {title}: {content}" )
