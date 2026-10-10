import logging, csv
from pathlib import Path
import json as jsonmodule
from jkm.tools import json2printdict
#import openpyxl

CSV_DIALECT_DEFAULT =  csv.excel()
CSV_DIALECT_DEFAULT.quoting = csv.QUOTE_STRINGS
CSV_ENCODING = "utf8"
CSV_NEWLINE = ""
CSC_ENCODING_ERRORS = "convert"
log = logging.getLogger() # Overwrite if needed. Setup is in the main script.

def isemptyfile(fpath):  
    "Note: may fail is something happens to the file while we check"
    return fpath.is_file() and ( fpath.stat().st_size == 0 ) 

class SpreadsheetCSV(): 
    # TODO: Convert to use the DictWriter class (needs data-pre-work to handle duplicate 'keys')
    """ """
    def __init__(self, filename, dialect = CSV_DIALECT_DEFAULT): 
        self.fp = Path(filename)
        self.csvfile = None
        self.dialect = dialect
        if self.fp.suffix != ".csv": 
            log.critical(f"CSV output file name must end in '.csv'. {self.fp} fails")
            sys.exit() 
    def writeheader(self):
        # Can update  self.writer.fieldnames as long as header has not yert been written. 
        self.writer.writeheader() 
    def isEmpty(self):
        return isemptyfile(self.fp)
    def isOpen(self):
        if self.csvfile: return True
    def close(self):
        self.save()
        self.csvfile = None
    def open(self, fieldnames): 
        self.csvfile = self.fp.open("a", # Append mode
                                    encoding= CSV_ENCODING,
                                    newline=CSV_NEWLINE,
                                    errors = CSC_ENCODING_ERRORS
                                    )  
        self.writer = csv.DictWriter(self.csvfile, fieldnames, dialect = self.dialect,  extrasaction='raise')
    def add_line_from_dict(self, datarowdict):
        for k in datarowdict.keys():
            print(f"{k} = ", datarowdict[k])
#        datarowdict = {k:v for k,v in datarowdict.items()}
        self.writer.writerow(  datarowdict )
        self.csvfile.flush() # Write data to file immediately
    def add_line_from_json(self, datarowdict):
        self.add_line_from_dict ( json2printdict(datarowdict) ) 
    def save(self):  
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
