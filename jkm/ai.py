# -*- coding: utf-8 -*-
import  logging,  json
log = logging.getLogger() # Overwrite if needed
#import imgtools
from google import genai
from google.genai import types

# For testing, Google Free Key for small tests
_TEST_APIKEY = "AIzaSyAqHT6cYM90MFH3Vx-12AgS9Ly0doaYw0k" 
_TESTING = True
_IMAGE_TRANSFER_UPLOAD = 1
_IMAGE_TRANSFER_INLINE = 2
_TEST_PROMPT = "There images are all of the same object. Find text in the images. Reply with JSON only, fitting the data into the following variables: collector, date, locality, identifier, and notes."
AI_FAILURE_RETURN_VALUE = 'null'

def load_apikey(fp):
    with fp.open() as f:
            return f.read()
    
def _parseAI_JSON(text):
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
class AIError(Exception): pass # Generic Error for passing along AI-related issues (like lack of prompt provided)
class AI_output:
    """A class for storing AI output. 
    
    Can hold both unstructured and structured content. If either is missing, returns None. """
    def __init__(self):
        self._text = None
        self._dict = None
    def to_dictionary(self):
        return self._dict 
        return True # Success
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
        self._MODEL = 'gemini-2.5-flash'
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
        if  self.client is None: raise AIError("Upload images requested before AI Client was created in code.")
        fileobj = self.client.files.upload(  file = filepath )
        if not fileobj: AIError(f"Uploading image failed, status {fileobj}")
        log.debug (f"OK upload {filepath}",  ) 
        return fileobj
        
    def _urify_image(self,  filepath): 
        bytes  = self._file2bytes(filepath)     
        return types.Part.from_bytes( data = bytes, mime_type = "image/jpeg")

   # Sending a query
    def query_images(self, pathlist):
        """Get data from Gemini based on multiple images. 
        
        Parameters: 
            pathlist: list of image files paths (Pathlib.Path instances)
            prompt: string
        Returns: 
            an AI_output object.
        """
        log.debug("Query_images started")
        # State checks
        if not self.prompt: raise AIError("No prompt for AI provided.")
        img_bytes = [self._file2bytes(x) for x in pathlist]
        sumsize = int(sum( [len(x) for x in img_bytes] )/1024)
        log.debug( f"Images to bytes done, size {sumsize} kb" )

        # Create AI client
        log.debug("Create client")
        self.client = genai.Client(api_key=self.apikey )
#        log.debug("Client is",  self.client )
        if not self.client: raise AIError("Creating an AI client failed.")
        log.debug("Create client done")

        # Upload files
        if self._IMAGE_TRANSFER_TYPE == _IMAGE_TRANSFER_UPLOAD:
            log.debug("Starting image(s) upload")
            readiedfiles = [self._upload_image(x) for x in pathlist]
            log.debug("Starting image(s) done")
        elif self._IMAGE_TRANSFER_TYPE == _IMAGE_TRANSFER_INLINE: 
            readiedfiles = [self._urify_image(x) for x in pathlist]
        else: raise AIError("Unknown image transfer type specified.")            

        # Add prompt and image information to query parameter 'contents'
        contentlist = [ self.prompt ] 
        for up_img in readiedfiles:  contentlist.append(up_img)
        # Query the model
#        response = self.client .models.generate_content( model= self._MODEL, contents = contentlist )           
#        text = response.text
        # Values for testing
        response = 'foo' #
        text = """```json {  "collector": "F. Kangas",  "date": "8. 7. 1932",  "locality": "Helsinki",  "identifier": "GV 101220",  "notes": "http://id.luom"}```"""

        log.debug( f'Response was "{text }"' )
        output = AI_output()
        if response == AI_FAILURE_RETURN_VALUE: return output        # Primitive error handling
        output.from_text( text ) # Tries parsing the tecxt as JSON
        return output
        
