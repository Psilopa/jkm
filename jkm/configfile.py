from pathlib import Path
#import configparser
import logging,  sys, argparse
import jkm.tools  as tools
import jkm.errors as errors
import tomllib

log = logging.getLogger() # Overwrite if needed

class tomlConfig(): # TOML-based replacement
    def __init__(self, fn=None):
        if fn: self.loadfile(fn)
    def loadfile(self,fn, encoding="utf8"):
        fp = Path(fn)
        if not fp.exists() or not fp.is_file():
            raise FileNotFoundError("File not found")
        with fp.open("rb") as f: 
            self._c = tomllib.load(f) # CAN FAIL
    def get(self,x, y = None):
        # Primitive, should handle more nested levels and errors
        if not y: return self._c.get(x)
        else: return self._c[x].get(y)
#        except configparser.Error as msg: raise errors.LoggingError(msg, level = logging.CRITICAL) 
    def getstr(self,*args): return str(self.get(*args)) 
    def getb(self,*args): return bool(self.get(*args)) 
    def geti(self,*args): return int(self.get(*args)) 
    def getf(self,*args): return float(self.get(*args)) 
    def getpath(self,*args): return Path(self.get(*args))
    def getlist(self,*args): return self.get(*args)        
    def has_section(self, section): return self._c.has_section(section)
    def sections(self): return self._c.sections()
    @property
    def basepath(self): return Path(self.get("data","main_data_directory"))  # TODO: Should we create if not_exists()    
 

class OLD_Multicamconfig():
    def __init__(self, fn=None):
        self._c = configparser.ConfigParser(interpolation=None)
        if fn: self.loadfile(fn)
        self.monitor = False
    def loadfile(self,fn, encoding="utf8"):
            fnp = Path(fn)
            if not fnp.exists() or not fnp.is_file(): raise FileNotFoundError("File not found")
            with fnp.open(encoding=encoding) as f:
                self._c = configparser.ConfigParser(interpolation=None)
                self._c.read_file(f)
    def get(self,*args,**kwargs): 
        try: return self._c.get(*args, **kwargs)
        except configparser.Error as msg: raise errors.LoggingError(msg, level = logging.CRITICAL) 
    def getstr(self,*args,**kwargs): return str(self._c.get(*args, **kwargs)) 
    def getb(self,*args,**kwargs): return self._c.getboolean(*args, **kwargs)
    def geti(self,*args,**kwargs): return self._c.getint(*args, **kwargs)
    def getf(self,*args,**kwargs): return self._c.getfloat(*args, **kwargs)
    def getpath(self,*args,**kwargs): return Path(self._c.get(*args, **kwargs))
    def getlist(self,*args,**kwargs):
        return tools.string2list(self._c.get(*args, **kwargs))
    def has_section(self, section): return self._c.has_section(section)
    def sections(self): return self._c.sections()
    @property
    def basepath(self): return Path(self._c.get("basic","main_data_directory"))  # TODO: Should we create if not_exists()    
 

# --- parse command-line arguments ---
def parse_args(programname): # 
    """Get command-line arguments using argparse.ArgumentParser."""
    parser = argparse.ArgumentParser(description = programname)
    parser.add_argument('-c', '--config_file',          
            required = True,
            help = 'name of configuration life',
            type=Path,
            )
    return parser.parse_args()

def load_configuration(programname):
    """Returns a config class instance with loaded data. Exits on failure as config data must be available."""    
    try:
        cmdargs  = parse_args(programname)
        conf_fn = cmdargs.config_file
        log.info(f"Reading configuration file {conf_fn}")
        return tomlConfig(conf_fn)
    except Exception as err:
        log.critical(f"Loading configuration file {conf_fn} failed: {err}")
        sys.exit()
        
