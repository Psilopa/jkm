# -*- coding: utf-8 -*-
"""OpenAI implementation of the AI access module. In dev."""
# SEE https://developers.openai.com/api/docs/quickstart?language=python FOR A SIMPLE OPENAI approach
# TODO?: KEEP FOR A SESSION. SEE https://developers.openai.com/api/docs/guides/agents-api/quickstart

# Standard library stuff
import logging
import json
import  mimetypes  # mime type based on file URL
import os
# my own local modules
from . import aibase
from . import security
from . import labeldata_model
from .errors import AIError, AIWarning, FileLoadingError
from .mytyping import * # For typing
from .meta import name as progname
log = logging.getLogger(progname) 

# AI supplier modules
from openai import OpenAI, OpenAIError

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

class OpenAI(aibase.AIbase):    
    aierrors = tuple( openai.error.Timeout )
    AI_FAILURE_RETURN_VALUE = 'null' # CHECK
    TESTING_REPLY_JSON = test_json
    TESTING_JSON_FROM_AI = json.dumps(json.loads(TESTING_REPLY_JSON)["output_text"] )
    def __init__(self:Self):
        super().__init__()
        self.modelname = 'gpt-6-luna' # Default model

    def close(self:Self) -> None:
#        os.environ.pop('OPENAI_API_KEY', None) # For safety, remove ENV variable on close.
        if self.client: self.client.close() # Not necessary, but a good habit.

    def _execute_query(self:Self,content=Collection) -> tuple[ str,str|None ]:
        assert self.client, "_execute_query without self.client: _create_client should fail with an exception to prevent this if client creation fails"
        try:
            reply = self.client.resposes.create(
                                                   model = self.model,
                                                   input = [{
                                                       "role": "user",
                                                       "content": content,
                                                       }],
                                                   text_format= labeldata_model.LabelData.model_json_schema()
                                                   )
            if not "output_text" in dir(reply) or reply.error: 
                return (json.dumps(reply), None)
            else: 
                return (json.dumps(reply), reply["output_text"] )
        except OpenAIError as msg:
            raise AIError(msg)
    
    def content_text(self:Self,txt:str):
        return {"type": "input_text",
                "text": self.prompt }
            
    def content_nonlocal_file(self:Self, url:type_url) -> dict[str,str]:
        """Returns a HTTP reqest fragment for passing an url."""
        return { "type": "input_image",
                 "image_url": str(url)
#                "detail": "original",
                 }
    
    def content_inline_image(self:Self,  filepath:Path) -> dict[str,str]: 
        """Returns a HTTP reqest fragment, for passing a local file to be transferred as bytes."""
        with filepath.open('rb') as f:
            fbytes = f.read()
        base64_image = base64.b64encode(fbytes).decode('utf-8')
        return {"type": "input_image",
                "image_url": f"data:image/jpeg;base64,{base64_image}" ,
#               "detail": "original",
                }

# OpenAI/Copilot APIKEY security solution.    
class apikey_OpenAI(OpenAI):
    def __init__(self:Self,  apikey:str|None = None):
        self.apikey = apikey
#        os.environ["OPENAI_API_KEY"] = apikey
        super().__init__()

    def _create_client(self:Self, timeout:int|None=None):
        return OpenAI(api_key = self.apikey, timeout=timeout)

