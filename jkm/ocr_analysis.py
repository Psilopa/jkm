"""
Stub OCR result lexeme parsing & context. To be run off an currently non-existing web API. 

Add further mapping from API output field titles -> relevant data input column names (for Kotka to start with)
"""
import logging,  urllib.request, urllib.parse, urllib.error, json 
#import cv2
#import jkm.tools
#from pathlib import Path
#import time, sys

log = logging.getLogger() # Overwrite if needed. Setup is in the main script.
_test_dummy_JSON = '[["leg","Skartveit, John"], ["contry","30"], ["locality","New York"]]'

class OCRAnalysisResult():
    def __init__(self,valuepairs = []): 
        self._data = valuepairs
    def add_field_value(self,field,value):
        self._data.append( (field,value) )
    def __str__(self): return str(self._data)
    def as_json(self): return json.dumps(self._data)
    @staticmethod
    def from_json(jsondata): 
        # FOR TESTING
        jsondata = _test_dummy_JSON
        x = json.loads(jsondata)
        return x

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
