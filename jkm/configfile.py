from pathlib import Path
import logging,  sys, argparse
import jkm.tools  as tools
from jkm.errors import ConfigError, ConfigWarning
#import jkm.errors as errors
import tomllib

log = logging.getLogger() # Overwrite if needed

class tomlConfig(): # TOML-based replacement
    def __init__(self, fn=None):
        self._d = None # Should be a dictionary-like object    
        if fn: self.loadfile(fn)
    def loadfile(self,fn, encoding="utf8"):
        fp = Path(fn)
        if not fp.exists() or not fp.is_file():
            raise FileNotFoundError("File not found")
        with fp.open("rb") as f: 
            self._d = tomllib.load(f) # CAN FAIL

    def get(self,l1, l2 = None, l3 = None, func=str, default=None):
        if l2 is l3 is None: 
            return func(self._d.get(l1, default))
        elif l3 is None: 
            return func(self._d[l1].get(l2, default))
        else: 
            return func(self._d[l1][l2].get(l3, default))
    def getstr(self,*args, **kwargs): return self.get(*args, **kwargs, func=str)
    def getb(self,*args, **kwargs): return self.get(*args, **kwargs, func=bool) 
    def geti(self,*args, **kwargs): return self.get(*args, **kwargs, func=int) 
    def getf(self,*args, **kwargs): return self.get(*args, **kwargs, func=float) 
    def getpath(self,*args, **kwargs): return Path(self.get(*args, **kwargs, func=str) )
    def getlist(self,*args, **kwargs): return self.get(*args, **kwargs, func=list) 
    def has_section(self, key): return key in self.sections()
    def sections(self): return self._d.keys()
    @property
    def basepath(self): return Path(self.get("data","main_data_directory"))  # TODO: Should we create if not_exists()    
    # CONF VERIFICATION
    def on_error(self, list_tree):
        raise ConfigError(
            f"Missing required config file item '{ ':'.join(list_tree) }'.")
    def on_warning(self, list_tree):
        raise ConfigWarning(
            f"Missing expected config file item '{ ':'.join(list_tree) }'.")
    def _checkstring(self,item,current_dict, onfail, tree=[]):
        newtree = tree + [item] # List of section levels (plus last item)
        if item not in current_dict: onfail(newtree)
        
    def _verify_list(self, items, current_dict, onfail, tree=[]):
        """
        Verify that the given items exist in the conf object.

        Parameter onfail must be a function."""
        for item in items: # item = name of a item, or a list
            if type(item) is str:
                self._checkstring(item, current_dict, onfail, tree)
            elif type(item) is list and len(item) >1:
                section_name = item[0]
                nextname = item[1]
                ctree = tree + [section_name]
                newdict = current_dict[section_name]
                self._checkstring(nextname, newdict, onfail, ctree)

    def verify(self, must_have=[], should_have=[]): 
        """Verify that the given must_have and should_have list content exist in the conf object.

        Both lists may have sublists: ["section","value"]."""
        self._verify_list(must_have, self._d, self.on_error)
        self._verify_list(should_have, self._d, self.on_warning)
            
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

def load(programname):
    """Returns a config class instance with loaded data. Exits on failure as config data must be available."""    
    try:
        cmdargs  = parse_args(programname)
        conf_fn = cmdargs.config_file
        log.info(f"Reading configuration file {conf_fn}")
        return tomlConfig(conf_fn)
    except Exception as err:
        log.critical(f"Loading configuration file {conf_fn} failed: {err}")
        sys.exit()

