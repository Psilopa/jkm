"""
Stub OCR result lexeme parsing & context. To be run off an currently non-existing web API. 

Add further mapping from API output field titles -> relevant data input column names (for Kotka to start with)
"""
import logging,  urllib.request, urllib.parse, urllib.error, json, re 

# TODO: PASS EXCEPTION INSTEAD OF LOGGING HERE
log = logging.getLogger() # Overwrite if needed. Setup is in the main script.

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

def cleanup(text): 
    t = text
    t = re.sub(r"\n","",t)
#    t = re.sub(r"^[\w\s]","",t)  
    t = re.sub(r"[\n\s]+"," ",t)
    t = t.strip()
    return t

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
