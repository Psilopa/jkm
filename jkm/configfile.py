from pathlib import Path
import logging,  sys, argparse
import jkm.tools  as tools
from jkm.errors import ConfigError, ConfigWarning
#import jkm.errors as errors
import tomllib
log = logging.getLogger() # Overwrite if needed

# TODO: DOES NOT HANDLE DEFAULT ARGUMENTS RIGHT?
def _recursedict(d:dict, args:list|tuple):
    key = args[0]
    val = d[key]
    if len(args) == 1: #This was the last element
        return d[key]
    else: return  _recursedict(val, args[1:])

_NODEFAULT = 219826382
class tomlConfig(): # TOML-based replacement
    def __init__(self, fn:str|Path|None=None) -> None:
        self._d:dict = {} # Should be a dictionary-like object    
        if fn: self.loadfile(fn)
    def loadfile(self,fn:str|Path, encoding:str="utf8") -> None:
        fp = Path(fn)
        if not fp.exists() or not fp.is_file():
            raise FileNotFoundError("File not found")
        with fp.open("rb") as f: 
            self._d = tomllib.load(f) # CAN FAIL
    def get(self, *args:list, default=_NODEFAULT):
        try:
            return _recursedict(self._d, args) 
        except KeyError as error:
            if default != _NODEFAULT: return default
            else: raise error
    def getstr(self,*args, **kwargs) -> str: return str(self.get(*args, **kwargs) )
    def getb(self,*args, **kwargs) -> bool: return bool(self.get(*args, **kwargs) ) 
    def geti(self,*args, **kwargs) -> int : return int(self.get(*args, **kwargs)  )
    def getf(self,*args, **kwargs)-> float: return float(self.get(*args, **kwargs) )
    def getpath(self,*args, **kwargs) -> Path: return Path(self.getstr(*args, **kwargs) )
    def getdict(self,*args, **kwargs) -> dict: return dict( self.get(*args, **kwargs) ) 
    def getlist(self,*args, **kwargs) -> tuple: return tuple( self.get(*args, **kwargs)  )
    def has_section(self, key:str): return key in self.sections()
    def sections(self) -> tuple: return tuple(self._d.keys())
    @property
    def basepath(self) -> Path:
        return Path(self.getstr("data","main_data_directory") )  # TODO: Should we create if not_exists()    
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
def parse_args(programname:str) -> argparse.Namespace:
    """Get command-line arguments using argparse.ArgumentParser."""
    parser = argparse.ArgumentParser(description = programname)
    parser.add_argument('-c', '--config_file',          
            required = True,
            help = 'name of configuration life',
            type=Path,
            )
    return parser.parse_args()

def load(programname:str):
    """Returns a config class instance with loaded data. Exits on failure as config data must be available."""
    conf_fn = ""
    try:
        cmdargs: argparse.Namespace = parse_args(programname)
        conf_fn= cmdargs.config_file
        log.info(f"Reading configuration file {conf_fn}")
        return tomlConfig(conf_fn)
    except Exception as err:
        log.critical(f"Loading configuration file {conf_fn} failed: {err}")
        sys.exit()

