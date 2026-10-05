# -*- coding: utf-8 -*-

# TODO: Gemini AI has a JSON Schema too, but it is not yet used here
# See https://ai.google.dev/gemini-api/docs/interactions?ua=chat

import  logging,  json, os, base64
import jkm.errors
log = logging.getLogger() # Overwrite if needed
#import imgtools
from google import genai
from google.genai import types
from google.genai import errors as gemini_errors
from google.genai.types import HttpOptions
import jkm.labeldata_model

# For testing, Google Free Key for small tests
_TESTING_BYPASS_AI_CALL = True
_TESTING_JSON_FROM_AI = """
{
  "verbatim_all_text": [
    {
      "verbatim_text": "Korpilahti"
    },
    {
      "verbatim_text": "17.7. 1939"
    },
    {
      "verbatim_text": "Rönnholm"
    }  ],
  "verbatim_locality": "Korpilahti",
  "verbatim_collector": "Rönnholm",
  "verbatim_date": "17.7. 1939",
  "verbatim_field_identifier": "",
  "verbatim_coordinates": "",
  "notes": "There is a black streak/smudge partially obscuring the collector's name (Rönnholm)."
}
"""
_IMAGE_TRANSFER_UPLOAD = 1
_IMAGE_TRANSFER_INLINE = 2
_TEST_PROMPT = "There images are all of the same object. Find text in the images. Reply with JSON only, fitting the data into the following variables: collector, date, locality, identifier, and notes."
AI_FAILURE_RETURN_VALUE = 'null'
_AI_GEMINI_TIMEOUT = 10 * 1000 # 10 seconds

def load_apikey(fp):
    with fp.open() as f: return f.read()
    
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
        

        
class geminiAI(): # Make subclasses based on authentication method
    def __init__(self):
        self._promt = None
        self.client = None
        # Settings, should come from user setup is a production code
        self._MODEL = 'gemini-3.8-flash' # Default value
    def close(self):
        if self.client: self.client.close() # Not necesary, but a good habit.
    # Getters, setters for properties
    @property
    def prompt(self): return self._promt
    @prompt.setter
    def prompt(self,  prompt): self._promt = prompt    
    @property
    def model(self): return self._MODEL 
    @model.setter
    def model(self,  model): self._MODEL  = model    
    
   # Sending a query
    # Preprocessing images
    def _file2bytes(self,  filepath):        
        with filepath.open('rb') as f:   return f.read()
   
    def _generate_client(self):
        return None # CHildren should override
        
    def query_images(self, pathlist, timeout = None):
        """Get data from Gemini based on multiple images. 
        
        Parameters: 
            pathlist: list of image files paths (Pathlib.Path instances)
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
        log.info( f"Images to bytes done, size {sumsize} kb" )

        # FAKE CALL FOR TESTING, NO ACTUAL AI CALL
        if _TESTING_BYPASS_AI_CALL:
            response = 'foo' #
            text = _TESTING_JSON_FROM_AI            
        else:
            # Create AI client
            log.debug("Create client")
            if  timeout: httpopts = HttpOptions(timeout=timeout)      
            else: httpopts = HttpOptions()
            self.client = self._generate_client(httpopts)
            if not self.client: raise jkm.errors.AIError("Creating an AI client failed.")
            # log.debug("Create client done")
            content =  [ {"type": "text", "text": self.prompt} ]
            content += self.add_images(pathlist)
            try: # Query the model
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": jkm.labeldata_model.LabelData.model_json_schema()
                    }
                interaction  = self.client.interactions.create (
                    model = self._MODEL,
                    input = content,
                    response_format= response_format
                    )
                text = interaction.output_text
            except gemini_errors.ServerError as msg:
               raise jkm.errors.AIError(msg)
            except gemini_errors.ClientError as msg:
               raise jkm.errors.AIError(msg)
            except gemini_errors.APIError as msg:
               raise jkm.errors.AIError(msg)
        log.debug( f'Response was "{text }"' )
        output = AI_output()
        if text == AI_FAILURE_RETURN_VALUE: return output        # Primitive error handling
        output.from_text( text ) # Tries parsing the tecxt as JSON
        return output
        
class apikey_geminiAI(geminiAI):
    def __init__(self,  apikey = None):
        self.apikey = apikey
        super().__init__()
    def _generate_client(self, httpopts):
        return genai.Client(api_key=self.apikey,  http_options = httpopts)
    def _upload_image(self,  filepath): 
        """"Upload an image to AI. 
        
        TODO: Needs Error handling!"""
        log.debug (f"Trying to upload {filepath},  of type {type(filepath)}") 
        if  self.client is None: raise jkm.errors.AIError("Upload images requested before AI Client was created in code.")
        fileobj = self.client.files.upload(  file = filepath )
        if not fileobj: jkm.errors.AIError(f"Uploading image failed, status {fileobj}")
        log.debug (f"OK upload {filepath}",  )   
        return fileobj
    def add_images(self, filepaths):
        results = []
        readiedfiles = [self._upload_image(fp) for fp in pathlist ]
        for myfile in readiedfiles:
            results.append( {"type": "image", "uri": myfile.uri, "mime_type": myfile.mime_type} )
        return results
        

class cloud_auth_geminiAI(geminiAI):
    def __init__(self):
        log.debug("Using cloud_auth_geminiAI()")
        super().__init__()
    def _generate_client(self, httpopts):
        # Check if required OAuth env variables exist
        ev_cloudfproject = "GOOGLE_CLOUD_PROJECT"
        cloud_id = os.getenv(ev_cloudfproject)
        if not cloud_id: # Error state handled by calling code
            raise jkm.errors.AIError(f"Could not read environmental variable {ev_cloudfproject}")
        return genai.Client(http_options = httpopts)
    def _urify_image(self,  filepath):        
        fbytes  = self._file2bytes(filepath)       
        return {
            "type": "image",
            "data": base64.b64encode(fbytes).decode('utf-8'),
            "mime_type": "image/jpeg",
            }
    def add_images(self,filepaths):
        imgs = []
        for fpath in filepaths:
            filebytes = self._file2bytes(fpath)
            imgs.append( self._urify_image(fpath) )
        return imgs
