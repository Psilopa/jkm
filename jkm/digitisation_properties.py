from  pathlib import Path
import shutil

class DigipropFile:
    def __init__(self):
        self._ddict = {}
        self._hdr = ""            
    def read(self, fileobject):
        d = [x.split("=",1) for x in fileobject.readlines()]
        if len(d) > 0: 
            self._hdr = d[0][0]
        d = [x for x in d if len(x) == 2] #skip lines that did not split into "x = y" pairs. Note: strips the hdr line, if any
        self._ddict = {k:v for (k,v) in d}
        return self._ddict
    def update(self,key, value):
        self._ddict[key] = value
    def setheader(self,val): 
        self._hdr = val
    def write(self,fileobject,line_end= "\n"):
        # TODO: make tmp copy
        fileobject.write(self._hdr + line_end)
        for k,v in self._ddict.items():
            fileobject.write("%s=%s%s" % (k,v.strip(),line_end) )
    def datadict(self): return self._ddict        
    def header(self): return self._hdr    
    def save(self, fullpath):
            with open(fullpath,"w") as f: self.write(f)
        

# Testing
if __name__ == "__main__":
    fdir = Path(r"Z:\jkmulticam\test\dc1.2022-10-31_09-48-41_933e42")
    fn = Path(r"postprocessor.properties")
    fullpath = fdir / fn
    #make backup copy
    backuppath = fdir / Path("~" + str(fn))
    shutil.copy(fullpath, backuppath)
    # Read, update and write
    dpr = DigipropFile()    
    with open(fullpath,"r") as f: dpr.read(f)
    dpr.update("identifier","http://id.luomus.fi/F.508500")
    dpr.update("timestamp","")
    with open(fullpath,"w") as f: dpr.write(f)
            
    
