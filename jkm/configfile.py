from pathlib import Path
from configparser import ConfigParser
import logging,  sys, argparse
import jkm.tools  as tools

log = logging.getLogger() # Overwrite if needed

class Multicamconfig():
# TODO: write support    
    def __init__(self, fn=None):
        self._c = ConfigParser(interpolation=None)
        if fn: self.loadfile(fn)
        self.monitor = False
    def loadfile(self,fn, encoding="utf8"):
            fnp = Path(fn)
            if not fnp.exists() or not fnp.is_file(): raise FileNotFoundError("File not found")
            with fnp.open(encoding=encoding) as f:
                self._c = ConfigParser(interpolation=None)
                self._c.read_file(f)
    def get(self,*args,**kwargs): return self._c.get(*args, **kwargs)
    def getb(self,*args,**kwargs): return self._c.getboolean(*args, **kwargs)
    def geti(self,*args,**kwargs): return self._c.getint(*args, **kwargs)
    def getf(self,*args,**kwargs): return self._c.getfloat(*args, **kwargs)
    def getlist(self,*args,**kwargs):
        return tools.string2list(self._c.get(*args, **kwargs))
    def has_section(self, section): return self._c.has_section(section)
    @property
    def basepath(self): return Path(self._c.get("basic","main_data_directory"))  # TODO: Should we create if not_exists()    
 

# --- parse command-line arguments ---
# TODO: better support for lists
def parse_args(programname): # Get command-line arguments, if any
    parser = argparse.ArgumentParser(description = programname)
    parser.add_argument('-c', '--config_file',          
            required = True,
            help = 'name of configuration life',
            type=Path)
    return parser.parse_args()

def load_configuration(programname):
    """Returns a config class instance with loaded data. Exits on failure as config data must be available."""    
    try:
        #    sys.argv = [sys.argv[0], '-c', r"Z:\jkmulticam\jkcamera_win.ini"] # For testing in IDLE on Windows
        cmdargs  = parse_args(programname)
        conf_fn = cmdargs.config_file
        log.info(f"Reading configuration file {conf_fn}")
        m = Multicamconfig(conf_fn)
        return m
    except Exception as err:
        log.critical(f"Loading configuration file {conf_fn} failed: {err}")
        sys.exit()
        
