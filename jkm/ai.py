# -*- coding: utf-8 -*-

# TODO: Gemini AI has a JSON Schema too, but it is not yet used here
# See https://ai.google.dev/gemini-api/docs/interactions?ua=chat

import  logging,  json, jkm. errors
log = logging.getLogger() # Overwrite if needed
#import imgtools
from google import genai
from google.genai import types
from google.genai import errors as gemini_errors
from google.genai.types import HttpOptions

# For testing, Google Free Key for small tests
_TESTING_BYPASS_AI_CALL = False
_TESTING_JSON_FROM_AI = """```json {  "collector": "F. Kangas",  "date": "8. 7. 1932",  "locality": "Helsinki",  "identifier": "GV 101220",  "notes": "http://id.luom"}```"""
_IMAGE_TRANSFER_UPLOAD = 1
_IMAGE_TRANSFER_INLINE = 2
_TEST_PROMPT = "There images are all of the same object. Find text in the images. Reply with JSON only, fitting the data into the following variables: collector, date, locality, identifier, and notes."
AI_FAILURE_RETURN_VALUE = 'null'
_AI_GEMINI_TIMEOUT = 10 * 1000 # 10 seconds


def load_apikey(fp):
    with fp.open() as f:
            return f.read()
    
def _parseAI_JSON(text):
    """Cleanup and parse pseudo-JSON as returned from an AI."""
    try: 
        # pre-parser clean up: remove everything outside the outermost {}
        first = text.find("{") 
        last = text.rfind("}") 
        if first == -1: first = 0 # if {not found, return from the 1st character
        if last == len(text) or last == -1: text = text[first:] # no last }, of last at end of text
        else: text = text[first:last+1] # +1 to include the outermost }
        d = json.loads(text)
        return d
    except json.JSONDecodeError as msg:
        # Strip everything outside first { and last }        
        log.warning(f"AI-generated JSON parsing failed with error message {msg}. Returning empty result.")
        return {}
        
# --- AI-related classes ---- 
class AI_output:
    """A class for storing AI output. 
    
    Can hold both unstructured and structured content. If either is missing, returns None. """
    def __init__(self):
        self._text = None
        self._dict = None
    def to_dict(self):
        return self._dict 
    def from_dict(self, datadict):
        self._text = str(datadict)
        self._dict =  datadict
        return True # Success
    def from_text(self,  text):
        self._text = text
        self._dict = _parseAI_JSON(self._text)
        return True # Success
    def __str__(self): 
        if self._dict: return str(self._dict) 
        return str( self._text)
    def to_json(self):
        return json.dumps(self._dict)    
        
        
class geminiAI():
    def __init__(self,  apikey = None):
        self._promt = None
        self.client = None
        self.apikey = apikey
        # Settings, should come from user setup is a production code
        self._MODEL = 'gemini-3.1-flash-lite-preview'
#        self._MODEL = 'gemini-2.5-flash'
        self._MIMETYPE = 'image/jpeg',
        self._IMAGE_TRANSFER_TYPE = _IMAGE_TRANSFER_INLINE
    # Getters, setters for properties
    @property
    def prompt(self): return self._promt
    @prompt.setter
    def prompt(self,  prompt): self._promt = prompt    
    @property
    def model(self): return self._MODEL 
    @model.setter
    def model(self,  model): self._MODEL  = model    
    
    # Preprocessing images
    def _file2bytes(self,  filepath):        
        with filepath.open('rb') as f:   return f.read()
   
    def _upload_image(self,  filepath): 
        """"Upload an image to AI. 
        
        TODO: Needs Error handling!"""
        log.debug (f"Trying to upload {filepath},  of type {type(filepath)}") 
        if  self.client is None: raise jkm.errors.AIError("Upload images requested before AI Client was created in code.")
        fileobj = self.client.files.upload(  file = filepath )
        if not fileobj: jkm.errors.AIError(f"Uploading image failed, status {fileobj}")
        log.debug (f"OK upload {filepath}",  ) 
        return fileobj
        
    def _urify_image(self,  filepath): 
        bytes  = self._file2bytes(filepath)     
        return types.Part.from_bytes( data = bytes, mime_type = "image/jpeg")

   # Sending a query
    def query_images(self, pathlist, timeout = None):
        """Get data from Gemini based on multiple images. 
        
        Parameters: 
            pathlist: list of image files paths (Pathlib.Path instances)
            prompt: string
            timeout: if given, HTTP call timeout period in milliseconds
        Returns: 
            an AI_output object
	Exceptions: 
	   jkm.errors.AIError 
        """
        log.debug("Query_images started")
        # State checks
        if not self.prompt: raise jkm.errors.AIError("No prompt for AI provided.")
        img_bytes = [self._file2bytes(x) for x in pathlist]
        sumsize = int(sum( [len(x) for x in img_bytes] )/1024)
        log.debug( f"Images to bytes done, size {sumsize} kb" )

        # Create AI client
        log.debug("Create client")
        if  timeout: httpopts = HttpOptions(timeout=timeout)      
        else: httpopts = HttpOptions()
        self.client = genai.Client(api_key=self.apikey,  http_options = httpopts)
#        log.debug("Client is",  self.client )
        if not self.client: raise jkm.errors.AIError("Creating an AI client failed.")
        log.debug("Create client done")

        # Upload files
        if self._IMAGE_TRANSFER_TYPE == _IMAGE_TRANSFER_UPLOAD:
            log.debug("Starting image(s) upload")
            readiedfiles = [self._upload_image(x) for x in pathlist]
            log.debug("Starting image(s) done")
        elif self._IMAGE_TRANSFER_TYPE == _IMAGE_TRANSFER_INLINE: 
            readiedfiles = [self._urify_image(x) for x in pathlist]
        else: raise jkm.errors.AIError("Unknown image transfer type specified.")            

        # Add prompt and image information to query parameter 'contents'
        contentlist = [ self.prompt ] 
        for up_img in readiedfiles:  contentlist.append(up_img)
        # Values for testing
        if _TESTING_BYPASS_AI_CALL:
            response = 'foo' #
            text = _TESTING_JSON_FROM_AI
        else:
            # Query the model
            try:
                response = self.client .models.generate_content( model= self._MODEL, contents = contentlist )           
                text = response.text
            except gemini_errors.ServerError as msg:
               raise jkm.errors.AIError(msg)
            except gemini_errors.ClientError as msg:
               raise jkm.errors.AIError(msg)
            except gemini_errors.APIError as msg:
               raise jkm.errors.AIError(msg)
        log.debug( f'Response was "{text }"' )
        output = AI_output()
        if response == AI_FAILURE_RETURN_VALUE: return output        # Primitive error handling
        output.from_text( text ) # Tries parsing the tecxt as JSON
        return output
        
