import logging, csv, re
from pathlib import Path
import json as jsonmodule
from .tools import json2printdict
from .errors import TaskError
#import openpyxl

CSV_DIALECT_DEFAULT =  csv.excel()
CSV_DIALECT_DEFAULT.quoting = csv.QUOTE_STRINGS
CSV_ENCODING = "utf8"
CSV_NEWLINE = ""
CSC_ENCODING_ERRORS = "convert"
log = logging.getLogger() # Overwrite if needed. Setup is in the main script.
ACTION_NEWFILE = "newfile"

# These should go to tools (and probably replaced with better tools by someone else)
def sanitize_filename(text:str) -> str:
    dirty = "".join(["\\[/\\?%*:|\"<>0x7F0x00-0x1F]", chr(0x1F) * 15])
    return re.sub(text,"-",dirty) # Replace all chars in dirty with -.

def isemptyfile(fpath: Path) -> bool:  
    "Note: may fail is something happens to the file while we check"
    return fpath.is_file() and ( fpath.stat().st_size == 0 ) 

class SpreadsheetBase():
    pass

class SpreadsheetCSV(SpreadsheetBase): 
    # TODO: Convert to use the DictWriter class (needs data-pre-work to handle duplicate 'keys')
    """ """
    def __init__(self, filename: str|Path, dialect:csv.Dialect = CSV_DIALECT_DEFAULT) -> None: 
        self.fp = Path(filename)
        self.csvfile = None
        self.dialect = dialect
        self.fields = []
        if self.fp.suffix != ".csv": 
            raise TaskError(f"CSV output file name must end in '.csv'. {self.fp} fails")
    def writeheader(self) -> None:
        # Can update  self.writer.fieldnames as long as header has not yert been written. 
        self.writer.writeheader() 
    def isEmpty(self) -> bool:
        return isemptyfile(self.fp)
    def isOpen(self) -> bool:
        if self.csvfile: return True
        else: return False
    def close(self) -> None:
        self.save()
        self.csvfile = None
    def open(self, fieldnames: Sequence[str]) -> None:
        if self.csvfile: self.csvfile.close() # Close if file was already open!
        self.fields = list(fieldnames)
        self.csvfile = self.fp.open("a", # Append mode
                                    encoding= CSV_ENCODING,
                                    newline=CSV_NEWLINE,
                                    errors = CSC_ENCODING_ERRORS
                                    )  
        self.writer = csv.DictWriter(self.csvfile, fieldnames,
                                     dialect = self.dialect,
                                     extrasaction='raise')
    def add_line_from_dict(self, datarowdict: dict[str,object],on_new_key:str = ACTION_NEWFILE) -> None:
        """Write a row based on a dictionary of column_header: value items.

        If the column_header is not included in the existing file structure, raise a ValueError."""
        for k in datarowdict.keys():
            if k not in self.fields:
                log.warning(f"Missing spreadsheet column {k} requested.")
                if on_new_key == ACTION_NEWFILE:
                    log.warning(f"Closing current spreadsheet file.")
                    self.close()
                    self.fp = self.fp.with_stem(self.fp.stem + "_" + sanitize_filename(k) )
                    log.warning(f"Opening a new file {self.fp} with addec column {k}.")
                    self.fields.append(k)
                    self.open(self.fields)                    
        self.writer.writerow(  datarowdict )
        if self.csvfile: self.csvfile.flush() # Write data to file immediately
    def add_line_from_json(self, datarowdict: dict[str,object] ) -> None:
        self.add_line_from_dict ( json2printdict(datarowdict) ) 
    def save(self) -> None:  
        if self.csvfile: self.csvfile.close()

#class SpreadsheetCSV(): 
#    """ """
#    def __init__(self, filename): 
#        self.fp = Path(filename)
#        self.wb = None
#        if self.fp.suffix != ".xlsx": 
#            log.critical(f"Excel output file name must end in '.xlsx'. {self.fp} fails")
#            sys.exit()            
#    def open(self): 
#        if self.fp.is_file(): # Read existing
#            self.wb = openpyxl.load_workbook(self.fp, data_only=True)
#        else: # Try to create
#            self.wb = openpyxl.Workbook()
#    def add_line(self, ocra): 
#        # TODO
#        for k, v in ocra:
#            print(k, v)
#    def save(self): 
#        self.wb.save(self.fp)
