# -*- coding: utf-8 -*-
"""MS Copilot reimplementation of the AI access module. In dev."""
#SEE https://developers.openai.com/api/docs/quickstart?language=python FOR A SIMPLE OPENAI approach

# TODO: KEEP FOR A SESSION. SEE https://developers.openai.com/api/docs/guides/agents-api/quickstart

# Standard library stuff
import logging
import json
import os
import  mimetypes  # mime type based on file URL
from pathlib import Path
# my own local modules
from . import aibase
from . import security
from . import tools
from . import labeldata_model
from .errors import AIError, AIWarning, FileLoadingError
from .mytyping import * # For typing
# AI supplier modules
from agent_framework.openai import OpenAIChatCompletionClient
from azure.identity import AzureCliCredential
from agent_framework import Message, Content

log = logging.getLogger() # Overwrite if needed

# For testing, Google Free Key for small tests
TESTING_BYPASS_AI_CALL = False # Default to no bypass: use actual AI

class OpenAI(aibase.AIbase):    
    aierrors = tuple( openai.error.Timeout )
    AI_FAILURE_RETURN_VALUE = 'null' # CHECK
    TESTING_REPLY_JSON = r"""{"status": "completed", "model": "gemini-3.5-flash-lite", "id": "DUMMYID", "created": "2026-10-10T17:56:56Z", "updated": "2026-10-10T17:56:56Z", "usage": {"total_input_tokens": 1133, "input_tokens_by_modality": [{"modality": "image", "tokens": 1100}, {"modality": "text", "tokens": 33}], "total_cached_tokens": 0, "total_output_tokens": 229, "total_tool_use_tokens": 0, "total_thought_tokens": 0, "total_tokens": 1362}, "service_tier": "standard", "steps": [{"type": "thought", "signature": "EmAKXgFpFH0TCBtbvirA2u6a+1v3JSS4CcgWyreyJdZ0OolgZ7FlhgZrxPNuT+UWDr9GIj2vDZs7nqlOlthrCskbaQep9nF2VUoq7B5zOFo/2bINWEN1eO8E1lHHj+p4jR0="}, {"type": "model_output", "content": [{"text": "{\n  \"verbatim_all_text\": [\n    {\n      \"verbatim_text\": \"ID: http://id.luomus.fi/GV.92671\"\n    },\n    {\n      \"verbatim_text\": \"Helsinki\"\n    },\n    {\n      \"verbatim_text\": \"8.VI. 1932\"\n    },\n    {\n      \"verbatim_text\": \"E. Kangas\"\n    },\n    {\n      \"verbatim_text\": \"GV92671\"\n    }\n  ],\n  \"verbatim_locality\": \"Helsinki\",\n  \"verbatim_collector\": \"E. Kangas\",\n  \"verbatim_date\": \"8.VI. 1932\",\n  \"verbatim_coordinates\": \"\",\n  \"verbatim_field_identifier\": \"\",\n  \"verbatim_taxon\": \"\",\n  \"verbatim_identified_by\": \"\",\n  \"notes\": \"\"\n}", "type": "text"}]}], "output_text": "{\n  \"verbatim_all_text\": [\n    {\n      \"verbatim_text\": \"ID: http://id.luomus.fi/GV.92671\"\n    },\n    {\n      \"verbatim_text\": \"Helsinki\"\n    },\n    {\n      \"verbatim_text\": \"8.VI. 1932\"\n    },\n    {\n      \"verbatim_text\": \"E. Kangas\"\n    },\n    {\n      \"verbatim_text\": \"GV92671\"\n    }\n  ],\n  \"verbatim_locality\": \"Helsinki\",\n  \"verbatim_collector\": \"E. Kangas\",\n  \"verbatim_date\": \"8.VI. 1932\",\n  \"verbatim_coordinates\": \"\",\n  \"verbatim_field_identifier\": \"\",\n  \"verbatim_taxon\": \"\",\n  \"verbatim_identified_by\": \"\",\n  \"notes\": \"\"\n}"""
    TESTING_JSON_FROM_AI = json.dumps(json.loads(TESTING_REPLY_JSON)["output_text"] )
    def __init__(self:Self):
        super().__init__()
        self.modelname = 'gemini-3.1-flash-lite' # Default model
	self.azure_endpoint = None

    def close(self:Self) -> None:
        pass
#        if self.client: self.client.close() # Not necesary, but a good habit.

    def _execute_query(self:Self,content=Collection) -> tuple[ str,str|None ]:
        assert self.client, "_execute_query without self.client: _create_client should fail with an exception to prevent this if client creation fails"
        message = Message(role="user",contents=content)
        reply = agent.run(message, options= {"response_format": labeldata_model.LabelData} )
        if not "value" in dir(reply): 
            return (reply.json, None)
        else: 
            return (reply.json), reply.value )
    
    def content_from_text(self:Self,txt:str):
        return Content.from_text(text=self.prompt}) 
            
    def _handle_nonlocal_file(self:Self, url:type_url) -> dict[str,str]:
        """Returns a HTTP reqest fragment passing an url."""
        mimetype = str(mimetypes.guess_type(url))
        return Content.from_uri(uri= url,media_type= mimetype )
    
    def _http_inline_image(self:Self,  filepath:Path) -> dict[str,str]: 
        """Returns a HTTP reqest fragment, passing a local file to be transferred as bytes."""
        fbytes  = filepath.read_bytes()
        Content.from_data( data=fbytes, media_type="image/jpeg" )


# OpenAI/Copilot APIKEY security solution.    
class apikey_OpenAI(OpenAI):
    def __init__(self:Self,  apikey:str|None = None):
	self.credentials = credential=AzureCliCredential()
#        self.apikey = apikey
        super().__init__()

    def _create_client(self:Self, timeout:int|None=None):
        client= OpenAIChatCompletionClient(
                    model=self.modelname,
                    azure_endpoint=security.get("AZURE_OPENAI_ENDPOINT"),
                    api_version=security.get("AZURE_OPENAI_API_VERSION"),
                    credential=self.credentials,
                    request_timeout = timeout # Not ideal, assumes this exists
                    )
        return client.as_agent(name="VisionAgent",
                               instructions="You are a helpful agent that can analyze images" )


