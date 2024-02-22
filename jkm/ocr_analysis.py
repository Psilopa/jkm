"""
Stub OCR result lexeme parsing & context. To be run off an currently non-existing web API. 

Add further mapping from API output field titles -> relevant data input column names (for Kotka to start with)
"""
import sys,  logging,  urllib.request, urllib.parse, urllib.error, json 
from pathlib import Path
#import openpyxl
import csv

# TODO: PASS EXCEPTION INSTEAD OF LOGGING HERE
log = logging.getLogger() # Overwrite if needed. Setup is in the main script.
_test_dummy_JSON = '[["leg","Skartveit, John"], ["contry","30"], ["locality","New York"]]'

#class OutputExcel(): 
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
        
class OutputCSV(): 
    # TODO: Convert to use the DictWriter class (needs data-pre-work to handle duplicate 'keys')
    """ """
    def __init__(self, filename): 
        self.fp = Path(filename)
        self.csvfile = None
        if self.fp.suffix != ".csv": 
            log.critical(f"CSV output file name must end in '.csv'. {self.fp} fails")
            sys.exit() 
    def open(self): 
        self.csvfile = self.fp.open("a") 
        self.writer = csv.writer(self.csvfile)
    def add_line(self, ocrdata):  
        self.writer.writerow( [str(x[1]) for x in ocrdata.as_list()] )
        self.csvfile.flush() # Write data to file immediately
    def save(self):  
        if self.csvfile: self.csvfile.close()

class OCRAnalysisResult():
    """ """
    def __init__(self): 
        self._data = []
    @staticmethod
    def from_json(jsondata): 
        # FOR TESTING
        jsondata = _test_dummy_JSON
        out = OCRAnalysisResult()
        for k, v in json.loads(jsondata): out.append(k, v)
        return out
    def as_json(self): return json.dumps(self._data)
    def __str__(self): return str(self._data)
    def as_list(self):
        return self._data
    def append(self,field,value):
        self._data.append( (field,value) )
    def prepend(self,field,value):
        self._data.insert(0,  (field,value) )

def ocr_analysis_Luomus(text): 
    """Call an external service to get raw OCR analysis, mapping lexemes to (Kotka) fields. 

Return value: an OCRAnalysisResult instance. """
    _timeout = 5
    apiurl = f"http://dummy.luomus.fi/service.api?text={urllib.parse.quote(text)}"
    try:     
#        req =  urllib.request.urlopen(apiurl,timeout = _timeout)
        return OCRAnalysisResult.from_json(_test_dummy_JSON)
    except urllib.error.URLError: 
        return OCRAnalysisResult()
