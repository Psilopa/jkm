# -*- coding: utf-8 -*-
# Standard library stuff
#import sys, ,  json, os,
import logging
import json # Only for testing?
import base64
import mimetypes  # mime type based on file URL
from pathlib import Path

# my own local modules
from . import aibase
from . import security
from . import labeldata_model
from .errors import AIError, AIWarning, FileLoadingError
from .mytyping import * # For typing
from .meta import name as progname

# AI supplier modules
from google import genai
from google.genai import types
from google.genai import errors as gemini_errors
from google.genai.types import HttpOptions
from google.genai._gaos.lib.compat_errors import GeminiNextGenAPIClientError
# For local OAUTH token management, used by local_oauth_geminiAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


log = logging.getLogger(progname) 
test_json = """{"output_text":
{  "verbatim_all_text": [
    {      "verbatim_text": "Helsinki"    },
    {      "verbatim_text": "8. VI. 1932"    },
    {      "verbatim_text": "E. Kangas"    }  ],
  "verbatim_locality": "Helsinki",
  "verbatim_collector": "E. Kangas",
  "verbatim_date": "8. VI. 1932",
  "verbatim_coordinates": "774:383",
  "verbatim_notebook_reference_code": "3903",
  "notebook_reference_code_label_properties": "green",
  "verbatim_taxon": "Xan. montana Húb.",
  "verbatim_identified_by": "I. Kekkilä"}}
"""



class geminiAI(aibase.AIbase): # Make subclasses based on authentication method
    TESTING_RAW = test_json# GRAB REAL EXAMPLE FROM A FILEmax_dim
    TESTING_TEXT = json.dumps(json.loads(TESTING_RAW)["output_text"] )

    TESTING_BYPASS_AI_CALL = False
    AI_FAILURE_RETURN_VALUE = 'null'
    # Grab the "output_text" section as JSON
    aierrors = (gemini_errors.ServerError,
                    gemini_errors.ClientError,
                    gemini_errors.APIError,
                    gemini_errors.ServerError,
                    GeminiNextGenAPIClientError)
    modelname = 'gemini-3.1-flash-lite' # Default model

    def __init__(self:Self):
        super().__init__()
        # self.client from parent class
        # self.promt from parent class

    def close(self:Self) -> None:
        "Close the http AI client connection."
        # Not necessary, but a good habit.
        if self.client: self.client.close() 

    def _execute_query(self:Self,content=Collection) -> tuple[ str,str|None ]:
        """Run the AI request and return the output

        Output format tuple(all_output_as_json, output_text_as_json).
        """        
        # Default query function. Uses the experimental Interactions API
        # May not work with older models
        # Raises a GeminiNextGenAPIClientError on API error
        assert self.client, "_execute_query without self.client: _create_client should fail with an exception to prevent this if client creation fails"
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": labeldata_model.LabelData.model_json_schema()
            }
        interaction  = self.client.interactions.create (
            model = self.modelname,
            input = content,
            response_format= response_format,
            )
        # Return raw_output, output_text
        if not "output_text" in dir(interaction): 
            return (interaction.json(), None)
        else: 
            return (interaction.json(), interaction.output_text )
    
    # Format data into a content that can be passed through a HTTP request
    def content_text(self:Self,txt:str):
         return {"type": "text", "text": txt}

    def content_nonlocal_file(self:Self,
                                   url:type_url,
                                   ctype:str="image") -> dict[str,str]:
        """Returns a HTTP reqest fragment wrapping the url with resource type and mimertype."""
        return {"type": str(ctype),
            "uri": str(url),
            "mime_type": str(mimetypes.guess_type(url)),
                }
        return http_input_fragment

    def content_inline_image(self:Self,  filepath:Path) -> dict[str,str]:
        with filepath.open('rb') as f:
            fbytes = f.read()
        return {
            "type": "image",
            "data": base64.b64encode(fbytes).decode('utf-8'),
            "mime_type": "image/jpeg",
            }

# ---------------------- Security solution subclasses --------------------
# APIKEY security solution.    
class apikey_geminiAI(geminiAI):
    def __init__(self:Self,  apikey:str|None = None):
        self.apikey = apikey
        super().__init__()

    def _create_client(self:Self, timeout:int|None=None) -> genai.Client:
        "Crfeate a http AI client object."
        if  timeout:
            httpopts = HttpOptions(timeout=timeout)      
        else:
            httpopts = HttpOptions()
        return genai.Client(api_key=self.apikey,  http_options = httpopts)


# OAUTH2 VARIANT BASE CLASS
class oauth_geminiAI(geminiAI):
    def __init__(self:Self, projectID:str, location:str):
        super().__init__()
        self.projectID = projectID 
        self.location = location # "global"

    def _create_client(self:Self, timeout:int|None=None) -> genai.Client:
        "Crfeate a http AI client object."
        if  timeout:
            httpopts = HttpOptions(timeout=timeout)      
        else:
            httpopts = HttpOptions()
        return genai.Client(
                    http_options = httpopts, 
                    project=self.projectID,
                    location=str(self.location), 
                    enterprise=True,
                    )

# OAUTH2  with Google's gcloud command line tools available (see the AUTHENTICATION.md )
class cloud_oauth_geminiAI(oauth_geminiAI):
    def __init__(self:Self,projectID:str, location:str):
        log.debug("Using cloud_oauth_geminiAI()")
        super().__init__(projectID, location)


# OAUTH2 without gcloud --- we keep manual track of credentials.
class local_oauth_geminiAI(oauth_geminiAI):
    def __init__(self:Self) :
        log.debug("Using local_oauth_geminiAI()")
        self.projectID = security.get("JKM_GOOGLE_PROJECT_ID")
        self.location = security.get("JKM_GOOGLE_LOCATION")
        super().__init__(self.projectID, self.location)
        log.debug("Loading credentials for local_oauth_geminiAI()")
        self.creds = self.load_oauth2_creds()
        log.debug("DOne")

    def load_cached_token(self:Self): #
        rv = security.get_cachedsecret()
        if not rv: return None
        else : return json.loads(rv) # Trey to read this as JSON

    def save_cached_token(self:Self, tokenjson): #
        security.set_cachedsecret(tokenjson)        

    def load_oauth2_creds(self:Self): #  -> Credentials|None
        """Converts `client_secret.json` to a credential object.

        This function caches the generated tokens to minimize the use of the
        consent screen.
        
        Based on the Google-provided example at https://ai.google.dev/gemini-api/docs/oauth.
        """
        SCOPES = ["https://www.googleapis.com/auth/cloud-platform", 'https://www.googleapis.com/auth/generative-language.retriever']
        creds = None
        # Use existing credentials from the OS keyring, if they exist
        tokendata = self.load_cached_token()
        if tokendata:
            creds = Credentials.from_authorized_user_info(tokendata, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token: # Creds exist but are not valid
                creds.refresh(Request())
            else:
                client_config_json = security.get("JKM_GOOGLE_CLIENT_SECRET_JSON")
                client_config = json.loads(client_config_json)
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            self.save_cached_token(creds.to_json())
        return creds
    
    def _create_client(self:Self, timeout:int|None=None) -> genai.Client:
        "Crfeate a http AI client object."
        if  timeout:
            httpopts = HttpOptions(timeout=timeout)      
        else:
            httpopts = HttpOptions()
        return genai.Client(
            http_options = httpopts,
            vertexai = True,
            project = self.projectID,
            location = self.location,
            credentials=self.creds)

