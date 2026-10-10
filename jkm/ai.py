# -*- coding: utf-8 -*-

import  logging,  json, os, base64,tempfile
from pathlib import Path
import jkm.errors, jkm.tools
log = logging.getLogger() # Overwrite if needed
#import imgtools
from google import genai
from google.genai import types
from google.genai import errors as gemini_errors
from google.genai.types import HttpOptions
import jkm.labeldata_model

# For local OAUTH token management, used by local_oauth_geminiAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

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
  "verbatim_taxon": "Baccha elongata",
  "verbatim_identified_by": "J. Kahanpää leg.",
  "notes": "There is a black streak/smudge partially obscuring the collector's name (Rönnholm)."
}
"""
_IMAGE_TRANSFER_UPLOAD = 1
_IMAGE_TRANSFER_INLINE = 2
_TEST_PROMPT = "There images are all of the same object. Find text in the images. Reply with JSON only, fitting the data into the following variables: collector, date, locality, identifier, and notes."
AI_FAILURE_RETURN_VALUE = 'null'
_AI_GEMINI_TIMEOUT = 10 * 1000 # 10 seconds

def load_apikey(fp):
#    if not fp.exists(): return None # TODO: SHOULD REPORT ERROR TYPE
    with fp.open() as f: return f.read()
    
def _parseAI_JSON(text, schema):
    """Cleanup and parse pseudo-JSON as returned from an AI."""
    if schema: # Check if this is already valid JSON following a Schema
        try:
            data = schema.model_validate_json(text)
            return data.model_dump() # Retrun as a json.loads() equivalent
        except jkm.labeldata_model.ValidationError:
            log.error(f"AI data model failed: returned invalid JSON data.")
            # Fall through and try the simpler method below
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
        self.raw = ""
    def to_dict(self):
        return self._dict 
#    def from_dict(self, datadict):
#        self._text = str(datadict)
#        self._dict =  datadict
#        return True # Success
    def from_text(self,  text, schema = None):
        self._text = text
        self._dict = _parseAI_JSON(self._text, schema)
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
        self._MODEL = 'gemini-3.1-flash-lite' # Default model
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
    def _create_client(self, httpopts):
        assert False, "Child classes should replace this function."
    def _execute_query(self,content):
        # Default query function. Uses the experimental Interactions API
        # May not work with older models
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": jkm.labeldata_model.LabelData.model_json_schema()
            }
        interaction  = self.client.interactions.create (
            model = self._MODEL,
            input = content,
            response_format= response_format,
            )
        # TODO: What happens if interaction.output_text  does not exist?
        # Return raw_output, output_text
        if not "output_text" in dir(interaction): 
            return (interaction, None)
        else: 
            return (interaction, interaction.output_text )
    
    def _upload_image(self,  filepath): 
        """"Upload an image to AI. 
        
        TODO: Needs Error handling!"""
        log.debug (f"Trying to upload {filepath},  of type {type(filepath)}") 
        if  self.client is None: raise jkm.errors.AIError("Upload images requested before AI Client was created in code.")        
        fileobj = self.client.files.upload(  file = filepath )
        if not fileobj: jkm.errors.AIError(f"Uploading image failed, status {fileobj}")
        log.debug (f"OK upload {filepath}",  )   
        return fileobj
    def query_images(self, pathlist, timeout = None, image_max_dim = 0):
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
#        img_bytes = [self._file2bytes(x) for x in pathlist]
#        sumsize = int(sum( [len(x) for x in img_bytes] )/1024)
#        log.info( f"Images to bytes done, size {sumsize} kb" )

        # FAKE CALL FOR TESTING, NO ACTUAL AI CALL
        if _TESTING_BYPASS_AI_CALL:
            raw = 'foo' 
            text_output = _TESTING_JSON_FROM_AI            
        else:
            # Create AI client
            log.debug("Create client")
            if  timeout: httpopts = HttpOptions(timeout=timeout)      
            else: httpopts = HttpOptions()
            self.client = self._create_client(httpopts)
            if not self.client: raise jkm.errors.AIError("Creating an AI client failed.")
            # log.debug("Create client done")
            content =  [ {"type": "text", "text": self.prompt} ]
            content += self._add_images(pathlist, image_max_dim)
            try: # Query the model
                rv = self._execute_query(content)
                (raw, text_output) = self._execute_query(content)
            except gemini_errors.ServerError as msg:
                raise jkm.errors.AIError(msg)
            except gemini_errors.ClientError as msg:
                raise jkm.errors.AIError(msg)
            except gemini_errors.APIError as msg:
                raise jkm.errors.AIError(msg)
        log.debug( f'Response was "{text_output}"' )
        outputcontainer = AI_output()
        if text_output == AI_FAILURE_RETURN_VALUE: return outputcontainer        # Primitive error handling
        # TODO: Handle errors here
        outputcontainer.from_text( text_output,
                                   schema = jkm.labeldata_model.LabelData ) # Tries parsing the text as JSON
        outputcontainer.raw = raw
        return outputcontainer
    def _file2bytes(self,  filepath):        
        with filepath.open('rb') as f:   return f.read()
    def _urify_image(self,  filepath):        
        fbytes  = self._file2bytes(filepath)       
        return {
            "type": "image",
            "data": base64.b64encode(fbytes).decode('utf-8'),
            "mime_type": "image/jpeg",
            }
    def _smallertempfile(self, fpath, image_max_dim, dir = None):
                img = jkm.tools.load_img(fpath)
                small = jkm.tools.shrink_to_maxdim(img, image_max_dim)
                # Save to temp directory
                suffix = fpath.suffix
                tmpf = tempfile.NamedTemporaryFile(delete_on_close=False, suffix = suffix)
                tmpf.close() # Now it should be writeable by other processes
                jkm.tools.save_img(tmpf.name, img)
                log.debug(f"Resizing done, saved to {tmpf.name}.")
                return tmpf
    def _add_images(self,filepaths, max_dim = 0): 
        """Default _add_images() passes files as query parameters."""
        assert max_dim >= 0
        imgs = []
        for fpath in filepaths:
            if max_dim == 0:# No scaling
                log.debug("No image resizing requested before AI.")
                imgs.append( self._urify_image(fpath) )
            else:
                log.debug(f"Resizing requested to a maximum dimension of {max_dim}.")
                smallerdir = None
                tmpf = self._smallertempfile(fpath, max_dim, dir = smallerdir)
                imgs.append( self._urify_image(Path(tmpf.name) ))
                del(tmpf) # Delete temp file onced we are done
        return imgs
    

# APIKEY security solution.    
class apikey_geminiAI(geminiAI):
    def __init__(self,  apikey = None):
        self.apikey = apikey
        super().__init__()
    def _create_client(self, httpopts):
        return genai.Client(api_key=self.apikey,  http_options = httpopts)
#    def _add_images(self, filepaths, image_max_dim=0):
#        results = []
#        assert image_max_dim >= 0
#        if 
#        readiedfiles = [self._upload_image(fp) for fp in filepaths]
#        for myfile in readiedfiles:
#            results.append( {"type": "image", "uri": myfile.uri, "mime_type": myfile.mime_type} )
#        return results

# OAUTH2 VARANT BASE CLASS
class oauth_geminiAI(geminiAI):
    def __init__(self, projectID, location):
        super().__init__()
        self.projectID = projectID 
        self.location = location # "global"
    def _create_client(self, httpopts):
        return genai.Client(
                    http_options = httpopts, 
                    project=self.projectID,
                    # Location can be 'global', which is a Python keywork and seems to confuse some Google tools, so we do an explicit string conversion here
                    location=str(self.location), 
                    enterprise=True,
                    )

# Gcloud-based 
class cloud_oauth_geminiAI(oauth_geminiAI):
    def __init__(self,projectID, location):
        log.debug("Using cloud_oauth_geminiAI()")
        super().__init__(projectID, location)

class local_oauth_geminiAI(oauth_geminiAI):
    def __init__(self, projectID, location, secretpath, tokenpath = None) :
        log.debug("Using local_oauth_geminiAI()")
        super().__init__(projectID, location)
        self.secretpath = secretpath
        self.tokenpath = tokenpath
        self.creds = self.load_oauth2_creds()
    def load_oauth2_creds(self):
        """Converts `client_secret.json` to a credential object.

        This function caches the generated tokens to minimize the use of the
        consent screen.
        
        Based on the Google-provided example at https://ai.google.dev/gemini-api/docs/oauth.
        """
        SCOPES = ["https://www.googleapis.com/auth/cloud-platform", 'https://www.googleapis.com/auth/generative-language.retriever']
        creds = None
        # Use existing credentials from self.tokenpath JSON file
        if self.tokenpath and os.path.exists(self.tokenpath):
            creds = Credentials.from_authorized_user_file(self.tokenpath, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.secretpath, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            if self.tokenpath:
                with self.tokenpath.open('w') as token:
                    token.write(creds.to_json())
        return creds
    def _create_client(self, httpopts):
        return genai.Client(
            http_options = httpopts,
            vertexai = True,
            project = self.projectID,
            location = self.location,
            credentials=self.creds)

