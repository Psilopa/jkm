# -*- coding: utf-8 -*-
# Standard library stuff
from abc import ABC, abstractmethod
import sys
import logging
import json
from pathlib import Path

# my own local modules
from . import tools
from . import labeldata_model
#from . import security
from .errors import AIError, AIWarning, FileLoadingError
from .mytyping import * # For typing
from .meta import name as progname

log = logging.getLogger(progname) # Overwrite if needed

_IMAGE_TRANSFER_UPLOAD = 1
_IMAGE_TRANSFER_INLINE = 2

# ******* THESE SHOULD BE COMMON AND SHARED BETWEEN AI SUPPLIERS  ******* 
def load_apikey(name, validate_min_len=20):
    # TODO: convert errors to jkm.errors.AIError
    rv = security.get(name)
    if not security.verify_appsecret(rv, minlen=validate_min_len): 
        raise AIError(f"APIKEY chosen as the validation method, but could not find a valid APIKEY in the configuration.",
                      level=logging.CRITICAL)
    else:
        return rv
    
def _parseAI_JSON(text:str, schema = None ) -> dict:
    """Converts the AI returned JSON to a dictionary structure like that returned by json.loads().

        Raises a jkm.errors.AIWarning on failure."""
    if schema is not None: # Check if this is already valid JSON following a Schema
        try:
            data = schema.model_validate_json(text)
            return data.model_dump() # Retrun as a json.loads() equivalent
        except labeldata_model.ValidationError:
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
        raise AIWarning(f"AI-generated JSON parsing failed with error message {msg}.")
        
# --- AI-related classes ---- 
class AI_output:
    # TODO: THIS IS LOGICAL MESS. We really should store the data in just 1 format
    # We should probably settle on storing the Python data structure + RAW, and convert to JSON as needed
    """A class for storing AI output. 
    
    Can hold both unstructured and structured content. If either is missing, returns None. """
    rawstr = "raw"
    vatext = "verbatim_all_text"
    def __init__(self:Self):
        self._text = None
        self._dict = None
        self.raw = ""

    def _pp_lines(self:Self,dictionary:dict, noraw:bool, insert:str="\t") -> list:
        # TODO this should 
        lines = []
        for k,v in dictionary.items():
            if noraw and (k == self.rawstr): continue # SUPPRESS 'raw' here
            if type(v) == dict: lines += self._pp_lines(v, noraw)
            elif k == "verbatim_all_text": # A bit of a hack
                lines.append( f"{insert}{k}:\n{v}" )
            else: lines.append(f"{insert}{k}:{v}")
        return lines

    def to_prettyprint(self:Self, newline:str = "\n", noraw:bool = True) -> str:
        if self._dict is None: return ""
        lines = self._pp_lines(self._dict, noraw)
        return newline.join(lines)

    def to_dict(self:Self) -> None:
        assert(self._dict)
        self._dict.update( {self.rawstr:self.raw} )
        return self._dict

    def from_text(self:Self,  text, schema = None) -> None:
        """Tries to convert the AI returned JSON to other formats.

        Raises a jkm.errors.AIWarning on failure."""
        self._text = text
        self._dict = _parseAI_JSON(self._text, schema) # Raises an AIWarning on failure
        # Prettyprint the verbatim_all_text field
        if self.vatext in self._dict:
            self._dict[self.vatext] = tools.list2printvalues(self._dict[self.vatext])       

    def __str__(self:Self) -> str: 
        if self._dict: return str(self._dict) 
        return str( self._text)

    def to_json(self:Self, suppress_raw:bool = False) -> str:
        if not self._dict: return "{}"
        if suppress_raw and (self.rawstr in self._dict):
            newdict = self._dict.copy()
            del newdict[self.rawstr]
            return json.dumps(newdict)
        else: return json.dumps(self._dict)


class AIbase(ABC):
    aierrors = tuple() # All Exception types we want to convert to AIErrors 
    AI_FAILURE_RETURN_VALUE = 'null'
    # Replace with AI-revelant output.
    TESTING_RAW = "{}" 
    # Replace with AI-revelant output. Should be valid LabelData JSON 
    TESTING_TEXT = "{}"
    # Output only XML-valid characters
    XML_VALID_CHARS_ONLY = True 

    def __init__(self:Self):
        self.client = None
        # The 2 below have getters and setters (in case we want fancy logic later)
        self.prompt = None

    # --- main worker function: takes in image urls, returns am AI_output object
    def labeldata_from_images(self:Self,
                     imageurls=Sequence[str],
                     timeout:int|None = None,
                     image_max_dim:int = 0,
                     force_download:bool = False) -> AI_output:
        """Get data from Gemini based on multiple images. 
        
        Parameters: 
            pathlist: list of image files paths (Pathlib.Path instances)
            timeout: if given, HTTP call timeout period in milliseconds
            force_download: True or False[default]: if True, images are downloaded and uploaded. If False, images are passed as URLs
        Returns: 
            an AI_output object
	Exceptions: 
##	   AIError

        """
        log.debug("Query_images started")
        # State checks
        if not self.prompt: raise AIError("No prompt for AI provided.")
        # FAKE CALL FOR TESTING, NO ACTUAL AI CALL
        if self.TESTING_BYPASS_AI_CALL:
            text_output = self.TESTING_TEXT            
            raw = self.TESTING_RAW
        else:
            # Create AI client
            log.debug("Create client")
            log.debug(f"AI client HTTP call timeout set to {timeout}.")
            self.client = self._create_client(timeout)
            if not self.client: raise AIError("Creating an AI client failed.")
            # log.debug("Create client done")
            content =  [ self.content_text(self.prompt)  ]
            for url in imageurls:
                c = self.content_from_url(url, force_download, image_max_dim)
                content.append( c )
            try: # Query the model
                rv = self._execute_query(content)
                (raw, text_output) = self._execute_query(content)
                print("**** TEXT OUTPUT = ", text_output)
            except self.aierrors as msg:
                raise AIError(msg)
        aioutput = AI_output()
        # Primitive error handling on failure, return empty result
        if text_output == self.AI_FAILURE_RETURN_VALUE:
            return aioutput   
        # TODO: Handle errors here
        # Sanitize text_output and raw: exclude UTF8 characters that are not
        text_output = self._xmlsafe(text_output)
        raw = self._xmlsafe(raw)
        # See https://www.w3.org/TR/xml11/?utm_source=chatgpt.com#charsets
        aioutput.from_text( text_output,
                            schema = labeldata_model.LabelData ) # Tries parsing the text as JSON
        aioutput.raw = raw
        return aioutput

    def _xmlsafe(self:Self,text:str):
        if self.XML_VALID_CHARS_ONLY:
            return tools.valid_xml_string(text)
        else:
            return text
        
    # --- abstract base classes -----
    @abstractmethod
    def _execute_query(self:Self,content=Collection) -> tuple[ str,str|None ]:
        """Run the AI request and return the output

        Output format tuple(all_output_as_json, output_text_as_json).
        """        
        raise NotImplementedError

    @abstractmethod
    def close(self:Self) -> None:
        "Close the http AI client connection."
        raise NotImplementedError

    @abstractmethod
    def _create_client(self:Self, timeout:int|None=None):
        "Crfeate a http AI client object."
        raise NotImplementedError

    # Format data into a content that can be passed through a HTTP request
    @abstractmethod
    def content_nonlocal_file(self:Self,
                                   url:type_url,
                                   ctype:str="image") -> dict[str,str]:
        """Returns a HTTP reqest fragment wrapping the url with resource type and mimertype."""
        raise NotImplementedError

    @abstractmethod
    def content_text(self:Self,txt:str):
        raise NotImplementedError

    @abstractmethod
    def content_inline_image(self:Self,  filepath:Path) -> dict[str,str]:
        raise NotImplementedError

    def content_local_file(self:Self, fpath:Path, max_dim:int = 0) -> dict[str,str]:
        if max_dim == 0:  # Should not rescale
            log.debug("No image resizing requested before AI.")
            return self.content_inline_image(fpath)
        log.debug(f"Resizing requested to a maximum dimension of {max_dim}.")
        img = tools.load_img(fpath) # Load from URL
        tmpf = tools.save_to_tempfile(img, max_dim=max_dim)
        if tmpf: # Temp file created and exists (but is not opened for writing)
            tmpfilepath = Path(tmpf.name) 
            return self.content_inline_image(tmpfilepath) 
            del tmpf  # Delete temp file onced we are done
        log.warning(f"Could not save a rescaled copy of {fpath}, using the original.")
        return self.content_inline_image(fpath)

    def content_from_url(self:Self,
                    url:type_url,
                    force_download:bool,
                    max_dim:int = 0
                    ) -> Sequence[dict[str,str]]: 
        """Convert an URL to resources usable in HTTP queries

        The return value is a dictionary describing a series of HTTP
        call key: value pairs. For an example of how what a single item should look like,
        see geminiAI._http_post_inline_image(),

        Keywords:
        max_dim: maximum dimension of a (local) image file. If >0: images that are larger than this will be downscaled.
        """
        assert max_dim >= 0
        log.debug(f"Trying to classify {url} as a local path or online resource.")
        try:
            islocal = tools.is_existing_path(url) # FileLoadingError on error.                
            if islocal:
                return self.content_local_file( tools.url2path(url), max_dim)
            else:
                log.warning(f"Trying to read unaccessible resource {fpath}.") # Should not handle
        except FileLoadingError: 
            # Not a local path .. try treating it as an online resource
            log.debug(f"\t {url} an online resource.")
            if force_download:
                # Download, save in temp file, then pass to AI
                image = tools.img_from_url(url)
                tempfile = tools.save_to_tempfile(image, max_dim=max_dim)
                if tempfile: # Temp file created and exists (but is not opened for writing)
                    tmpfpath = Path(tempfile.name)                       
                    return self.content_local_file(tmpfpath, max_dim)
            else: 
                return self.content_nonlocal_file(url)    




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
