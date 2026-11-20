# -*- coding: utf-8 -*-
# Standard library stuff
#import sys, ,  json, os,
import base64
import logging
import json # Only for testing?
import mimetypes  # mime type based on file URL
from pathlib import Path

# my own local modules
from . import aibase
from . import security
from . import tools
from . import labeldata_model
from .errors import AIError, AIWarning, FileLoadingError
from .mytyping import * # For typing

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

log = logging.getLogger() # Overwrite if needed


class geminiAI(aibase.AIbase): # Make subclasses based on authentication method
    TESTING_BYPASS_AI_CALL = False
    AI_FAILURE_RETURN_VALUE = 'null'
    TESTING_REPLY_JSON = r"""{"output_text":{}}"""
    # Grab the "output_text" section as JSON
    TESTING_JSON_FROM_AI = json.dumps(json.loads(TESTING_REPLY_JSON)["output_text"] )
    aierrors = (gemini_errors.ServerError,
                    gemini_errors.ClientError,
                    gemini_errors.APIError,
                    gemini_errors.ServerError,
                    GeminiNextGenAPIClientError)

    def __init__(self:Self):
        self.client = None
        # The 2 below have getters and setters (in case we want fancy logic later)
        self._promt = None
        self.modelname = 'gemini-3.1-flash-lite' # Default model

    def close(self:Self) -> None:
        if self.client: self.client.close() # Not necesary, but a good habit.

    def content_from_text(self:Self,txt:str):
         return {"type": "text", "text": txt}

    def _execute_query(self:Self,content=Collection) -> tuple[ str,str|None ]:
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
        # TODO: What happens if interaction.output_text  does not exist?
        # Return raw_output, output_text
        if not "output_text" in dir(interaction): 
            return (interaction.json(), None)
        else: 
            return (interaction.json(), interaction.output_text )
    
    def _handle_nonlocal_file(self:Self, url:type_url, ctype:str="image") -> dict[str,str]:
        """Returns a HTTP reqest fragment wrapping the url with resource type and mimertype."""
        return {"type": str(ctype),
            "uri": str(url),
            "mime_type": str(mimetypes.guess_type(url)),
                }
        return http_input_fragment

    def _http_inline_image(self:Self,  filepath:Path) -> dict[str,str]:
        with filepath.open('rb') as f:
            fbytes = f.read()
        return {
            "type": "image",
            "data": base64.b64encode(fbytes).decode('utf-8'),
            "mime_type": "image/jpeg",
            }

#    def _upload_image(self:Self,filepath:Path): # TODO: return value type
#        """"Upload an image to AI. 
#        
#        TODO: Needs Error handling!"""
#        log.debug (f"Trying to upload {filepath},  of type {type(filepath)}") 
#        if  self.client is None: raise AIError("Upload images requested before AI Client was created in code.")        
#        fileobj = self.client.files.upload(  file = filepath )
#        if not fileobj: raise AIError(f"Uploading image failed, status {fileobj}")
#        log.debug (f"OK upload {filepath}",  )   
#        return fileobj


# APIKEY security solution.    
class apikey_geminiAI(geminiAI):
    def __init__(self:Self,  apikey:str|None = None):
        self.apikey = apikey
        super().__init__()

    def _create_client(self:Self, timeout:int|None=None) -> genai.Client:
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

