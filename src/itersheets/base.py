# DEPENDS ON PYTHON 3.14? 
# STDlib
from abc import ABC, abstractmethod
from pathlib import Path
import logging, json

# My own modules
#from .mytyping import * # For type checking tools
from .errors import sheetError

log = logging.getLogger() # Set from main script if fancy logging is required.

class new_column_action:
    NEWFILE = "newfile" # Only supported for CSV at the moment
    INSERT = "insert" # Only supported for XLS at the moment
#   EXCEPTION = "reject" # TODO- not currently supported. Raise a UnknownColumnError ?

def json2printdict(jsondata: str | dict[str,Any] ) -> dict[str,Any]:
    "Converts a string with JSON data or a corresponding dictionary with prettyprinted content."
    # TODO: this is not pasticularly good
    if isinstance(jsondata, str):  jsondata = json.loads(jsondata) 
    # Reformat a JSON reply to for Table output
    rv: dict[str,str] = {}
    for key in jsondata.keys():
        if isinstance(jsondata[key], list):
            rv[key] = list2printvalues( jsondata[key] )
        else: rv[key] = jsondata[key]
    return rv

def list2printvalues( mylist: Collection[dict] )-> str:
    "Prettyprints the values from a list of dictionaries."
    out = []
    for valuedict in mylist:
        out +=  valuedict.values()
    return "\n".join(out)

# These should go to tools (and probably replaced with better tools by someone else)
def unique(s: Sequence) ->tuple[str,...] :return tuple(dict.fromkeys(s)) 

class Spreadsheet(ABC):
    def __init__(self:Self, filename: str|Path) : 
        self.fp = Path(filename)
        self.file = None
        self._opened = False
        self._fields = tuple()
        self._currentfields = set()

    @property
    def filename(self:Self) -> Path: return self.fp

    @property
    def is_open(self:Self) -> bool: return self._opened

    @property
    def exists(self:Self) -> bool:
        if not self.fp or not self.fp.exists(): return False
        else: return True

    @property
    def is_empty(self:Self) -> bool:
        if not self.exists: return True
        return self.fp.is_file() and ( self.fp.stat().st_size == 0 )

    @property
    def fields(self:Self)-> tuple[str,...]: return self._fields

    @abstractmethod        
    def open(self:Self, fieldnames: Sequence[str] = []) -> None:
        self._opened = True

    def close(self:Self) -> None:
        "Closes the associated file(s) and marks the Spreadsheet as not open."
        if self.file: self.file.close()
        self._opened = False

    def has_columns(self:Self, fields:Collection[str]) -> bool:
        "True is spreadsheet has a field for each value in fields."
        return self._currentfields.issuperset( set(fields) )

    def lacks_columns(self:Self, fields:Collection[str]) -> set[str]:
        "Returns a set of field names that are missing from the spreadsheet."
        return set(fields).difference( self._currentfields )

# ------------ WRITE ONLY SPREADSHEETS -------------    
class WriteOnlySpreadsheet(Spreadsheet):
    def __init__(self:Self, filename: str|Path) :
        super().__init__(filename)
        self._saved = False

    @property
    def is_saved(self:Self) -> bool: return self._saved

    @property
    def fields(self:Self)-> tuple[str,...]: return self._fields

    @fields.setter
    def fields(self:Self, val) -> None:
        self._fields = tuple(unique(val))
        self._currentfields = set(self._fields)

    # Override parent class methods in child classes
    def close(self:Self, save:bool=True) -> None:
        if save: self.save()
        if not self._saved: log.warning(f"Closing file {self.filename} without saving first.")
        super().close()

    @abstractmethod        
    def save(self:Self): pass
        
    @abstractmethod        
    def addrow(self:Self,
               datarowdict: dict[str,object],
               on_new_field:str 
               ) -> None:
        self._saved = False

   
    def add_row_from_dict(self:Self,
                           datarowdict: dict[str,object],
                           on_new_key:str ) -> None:
        """Write a row based on a dictionary of column_header: value items.

        If the column_header is not included in the existing file structure, raise a ValueError."""
        self.addrow( json2printdict(datarowdict), on_new_key )
        
    def add_row_from_json(self:Self, datarowdict: dict[str,object],
                           on_new_key:str  ) -> None:
        self.addrow( json2printdict(datarowdict), on_new_key )

    def move(self:Self, newpath, overwrite=False):
        if not self.exists: return # Nothing to do.
        if newpath.exists() and not overwrite:
            raise sheetError(f"Will not overwrite {newpath}")
        self.fp.replace(newpath)
# -------------- READING ----------------
class ReadOnlySpreadsheet(Spreadsheet):
    def __init__(self:Self, filename: str|Path) :
        super().__init__(filename)

    # Iterator approach
    @abstractmethod        
    def next(self:Self) -> Iterable[str]: 
        return iter([])

    @abstractmethod        
    def open(self:Self) -> None:
        self._opened = True

#    @abstractmethod        
#    def get_row(self,n:int, func:Callable|None=None, replace_none:str|None=None) -> tuple:
#        """Get row values as a tuple.
#
#        n - int. Row number, starting from 0.
#        func - if not None, a function that is called for every element
#        replace_none - None or string. If a string, None values is output are replaced with this value *before* the function func is called.
#        """
#        return tuple()


