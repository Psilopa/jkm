# -*- coding: utf-8 -*-
""" Class usage: create a jkm_post object and call its main() function. """
#
# Check: Watchdog in licences using the Apache License, Version 2.0 
# ADD ATEXIT CALL TO CLOSE LOG FILES ON CRASH OR OTHER CLEAN ERROR HANDLING
import logging
log = logging.getLogger() # Overwrite if needed

# Standard python modules
import time, threading, sys, queue
from math import inf
from datetime import datetime
from pathlib import Path
# non-stdlib modules
import watchdog.events, watchdog.observers
# app-specific modules
import jkm.configfile, jkm.sample,  jkm.tools
import jkm.spreadsheet, jkm.ai, jkm.log
import jkm.meta, jkm.errors, jkm.barcodes
import jkm.external as ext
# import jkm.ocr_analysis
# For typing
from jkm.typing import *

# CONSTANTS
BACKUP_DATATABLE = True
_AI_AUTH_TYPES = ("APIKEY", "CLOUD_OAUTH", "LOCAL_OAUTH")
class processor:
    SUCCESS = 0
    FAIL_IGNORE = 1
    FAIL_RETRY = 2
#------------------ MISC TOOLS  ------------------- 
# Default threadpool, using Python threading module.
class myThreadPool():
    @property
    def activethreadcount(self) -> int: return len(self.threads) 
    def __init__(self):
        self.threads = []
    def newthread(self:Self, target:Callable, args:list|tuple= ()) -> None:
        t = threading.Thread(target = target, args = args)
        t.start()
        self.threads.append(t)            
    def join(self) -> None:
        for t in self.threads: t.join()
        self.threads = []

# MAP sample format string from config to a sample class
# NEW CLASS DEVELOPERS: ADD YOUR CLASS HERE
def get_sample_class(sample_format_str:str) -> type_sample:
    str2class = {
        "dir_content":  jkm.sample.SingleImageSample,  # Every matching image in a directory (incl subdirs) = a sample
        "subdirectories":  jkm.sample.DirectorySample, # For each directory, all images = a sample
        "resourcefile":  jkm.sample.FileRowSample,  # 1 row = 1 sample
        "mzh_insectline" : jkm.sample.LuomusInsectLineSample,
        "mzh_plantline":  jkm.sample.LuomusPlantLineSample,
        }
    try:
        return str2class[ sample_format_str.lower() ]
    except KeyError:
        raise jkm.errors.FileLoadingError(f"Unknown sample file/directory format '{sample_format_str.upper()}'.")
    
class myFileEventHandler(watchdog.events.PatternMatchingEventHandler):
    _lastinsert = None
    def __init__(self:Self, queue: queue.Queue, **kwargs) -> None: 
        self.queue = queue
        super().__init__(**kwargs)
    def on_created(self:Self, event: watchdog.events.FileSystemEvent) -> None:
        """Queues path names when a new filesystem event is noticed."""
        if event.src_path != self._lastinsert: 
            url = jkm.tools.path2url( Path(str(event.src_path) ) )             
            self.queue.put(url)
        else: log.debug(f"Prevented double insertion of {event.src_path} into the queue")
        self._lastinsert = event.src_path        

def find_existing_events(conf:type_conf) -> tuple[type_url]:
    "Returns a tuple of urls pointing to a resource that can be used to build an event."
    datafile_patterns = conf.getlist("data", "sample_pattern")        
    # Find list of file names matching a pattern and put them into the queue
    sample_format = conf.getstr("data", "datatype_to_load")        
    sample_class = get_sample_class( sample_format.lower() )
    found = sample_class.find_samples(conf.basepath,datafile_patterns)          
    return found
        
#------------------ SINGLE TASKS -------------------
def task_backup_images(sample:type_sample, target_dir:Path, maxdim:int=0) -> None:
    """Save copied of the processed images.
    Keywords:   
    maxdim - if >0, maximum dimension of the saved image
    """
    for sampleimg in sample.imagelist:
        img = jkm.tools.load_img(sampleimg.url)
        if img is None: return None # Nothing to do
        if maxdim > 0: img = jkm.tools.shrink_to_maxdim(img, maxdim)
        # Create target safe path from the full image filename AND parent directory 
        try: 
            fpath = jkm.tools.url2path(sampleimg.url,
                                       allowed_schemes = ("file",)
                                       )
            pathparts = fpath.parts
            imgdir = pathparts[-2]        
            filename = "_".join( (imgdir,fpath.name) ) # dir+filename as a filename        
        except ValueError: # Probably not a local file
            # TODO: THIS ASSUMES LUOMUS-STYLE URL PATHS!
            fpath = jkm.tools.url2path(sampleimg.url)
            pathparts = fpath.parts
            imgdir = pathparts[-2]
            filename = "_".join( (imgdir,fpath.name) ) # dir+filename as a filename        
        outpath = target_dir / filename        
        jkm.tools.save_img(outpath, img)

def task_add_prefix_to_imagefiles(sample:type_sample) -> None:
    try:
        new_name_prefix = sample.shortidentifier
        sample.rename_all_files(new_name_prefix, prefix_separator= "_")
    except (jkm.errors.JKError, FileNotFoundError) as msg:
        log.error(f"{sample.name}: Renaming files failed: {msg}.")                

def task_OCR(conf:type_conf, sample:type_sample) -> str:
    alltext = ""
    ocr_command = conf.get("ocr", "ocr_command")
    for image in sample.imagelist:
        if not image.has_labels : continue # Skip pure specimen images
        labeltxt = image.ocr(ocr_command) # Default ocr uses fragments created above
        alltext += " " + labeltxt
    sample.meta.addlog("Combined OCR result for all images",alltext,  log_add_hdr= sample.name, lvl = logging.DEBUG)
    sample.results.ocrtext = alltext
    return alltext

def task_read_barcodes(conf:type_conf, sample:type_sample) -> Sequence[str]:
    allbarcodes = []
    barcodepackage = conf.get( "barcodes", "barcodepackage").lower()
    for image in sample.imagelist:
        try:
            # NOTE: the choice of barcose detector tool is hardcoded in jkm/barcodes.py
            bkdata = image.readbarcodes(barcodepackage)
            image.meta.addlog("Barcode contents", bkdata, log_add_hdr= sample.name, lvl=logging.DEBUG)
            allbarcodes += bkdata
        except jkm.errors.FileLoadingError as msg:
            log.warning(f"{sample.name}: Barcode detection attempt failed: %s" % msg)
            continue
    sample.results.ocrtext = allbarcodes
    return allbarcodes

def task_get_text_areas(conf:type_conf, sample:type_sample) -> Collection[type_rotated_rect]:
    textareas = []
    for image in sample.imagelist:
        if not image.has_labels : continue # Skip pure specimen images
        log.debug(f"{sample.name}: Searching for text areas in {image.label} of sample {sample.name}")
        neuralnet = conf.get( "ocr", "EASTfile")
        textareas = image.findtextareas(neuralnet)
        image.meta.addlog("Text areas found", str(textareas),  log_add_hdr= sample.name, lvl = logging.DEBUG)
        if conf.getb( "postprocessor", "save_text_area_images"): 
            image.savetextareas("_textarea_")
    return textareas

def task_AI_label_data_extraction(conf:type_conf, sample:type_sample) -> type_airresult|None:
    airesult = None # Start with no result
    try:
        ai_auth_type = conf.get("ai", "auth_type") 
        assert ai_auth_type in _AI_AUTH_TYPES
        if ai_auth_type == 'APIKEY': myai = jkm.ai.apikey_geminiAI(conf.APIKEY)
        elif ai_auth_type == 'CLOUD_OAUTH':
            project_id = conf.getpath("ai", "google_project_id")
            location = conf.getpath("ai", "google_location")
            myai = jkm.ai.cloud_oauth_geminiAI(project_id, location)
        elif ai_auth_type == 'LOCAL_OAUTH': 
            app_token_path = conf.getpath("ai", "app_token_path") # Should be readable
            tmp_token_path = conf.getpath("ai", "tmp_token_path") # Should be writeable
            project_id = conf.getstr("ai", "google_project_id")
            location = conf.getstr("ai", "google_location")
            myai = jkm.ai.local_oauth_geminiAI(project_id, location, app_token_path, tmp_token_path)
        else:
            myai = None # Should never happen as ai_auth_type is verified to havce a valid value at this point
        if myai: #
            myai.model = conf.getstr('ai','model')
            myai.prompt = conf.getstr('ai','prompt')
            imageurls = [x.url for x in sample.imagelist if x.has_labels]
            image_max_dim = conf.geti("ai", "max_image_dim", default=0)
            timeout = conf.geti("ai", "request_timeout", default=None) # milliseconds
            force_download = conf.geti("ai", "force_download", default=False) 
            airesult = myai.labeldata_from_images(imageurls,  image_max_dim = image_max_dim, timeout=timeout, force_download = force_download)
            myai.close()
        # airesult can contain almost anything, possibly including non-valid UTF8. Should sanitize better.
        log.debug(f"{sample.name}:AI call for data extraction returned {str(airesult)}")
        outfn = conf.get("ai","properties_filename")
        if outfn and (airesult is not None): # If a properties_filename was defined
            outpath = sample.datapath / outfn
            with outpath.open("w") as f: f.write(airesult.to_json())                                                        
        else: log.debug(f"{sample.name}:No AI properties file generation requested in config file")
    except (IOError,  jkm.errors.AIError, jkm.errors.AIWarning) as msg:
        log.warning(f"{sample.name} - AI issue: '{msg}'.")
        airesult = None
    sample.results.labeltext_ai1 = airesult
    return airesult
    
def task_rename_directories(conf:type_conf, sample:type_sample, sleep_before:int = 0) -> None:
    # Tries a few times in case directory renaming is blocked by other processes
    if sleep_before > 0: 
        log.debug(f"Sleeping {sleep_before} seconds before directory renaming to allow for other programs to finish.")
        time.sleep(sleep_before)
    prefix = sample.datapath.name # last element of directory path
    log.debug(f"{sample.name}: Renaming directory based on barcode content")
    attempt_times = 2
    wait_time = 2 # seconds
    attempt_current = 1
    while (attempt_current <= attempt_times) :
        try:            
            sample.rename_directories(conf,prefix)
            break # Exit the while loop 
        except (jkm.errors.JKError) as msg: 
            log.warning(f"{sample.name}: Renaming directory failed: {msg}.")                
            break # Exit the while loop 
        except FileExistsError as msg:
            log.warning(f"{sample.name}: Renaming directory failed, there is already a directory with this name: {msg}")                
            break # Exit the while loop 
        except FileNotFoundError as msg:
            log.warning(f"{sample.name}: Renaming directory failed, original directory does not exist anymore: {msg}")                
            break # Exit the while loop 
        except PermissionError as msg:                
            log.warning(f"No write access: {msg}. \nWill attempt again in {wait_time} seconds {attempt_times-attempt_current} times.")
        # If loop was not interrupted by break above
        attempt_current += 1
        time.sleep(wait_time)

def task_rotate(sample:type_sample, degrees:int, allowed_values:Collection|None = None) -> None:
    if allowed_values and (degrees not in allowed_values):
        raise jkm.errors.TaskError(
            f"Given image rotation amount not in allowed range ({allowed_values})")
    for image in sample.imagelist:
        log.debug(f"{sample.name}: Rotating image {image.name}")
        image.rotate(degrees)

def task_crop(sample:type_sample, p:dict[str,str]) -> None:
    log.debug(f"Crop called with parameters {p}")
    target = p.get("target")
    method = p.get("method")
    assert target in ["specimen", "label", "all"] , "Unknown crop target" # SHOULD NOT BE ASSERT
    assert method in ["fixed"] , "Unknown cro method" # SHOULD NOT BE ASSERT
    for image in sample.imagelist:
        log.debug(f"{sample.name}: Cropping image {image.name}")
#        image.cropfixed()

def task_write_spreadsheet(spreadsheet:type_spreadsheet,
                           airesult,
                           barcode_identifier:str|None=None,
                           write_raw_output:bool=True
                           )-> None:
    # We handle spreadsheet opening here because we do not know possible header fields at script start time!
    raw = "raw"
    if barcode_identifier: outdata = {"barcode_ID": barcode_identifier or ""}
    else: outdata = {}
    if airesult is not None:
        outdata.update(airesult.to_dict() )
        outdata.update( {raw: airesult.raw} )
    if (not write_raw_output) and (raw in outdata):
        del outdata[raw]
    if not spreadsheet.isOpen(): 
        spreadsheet.open(fieldnames = outdata )
        if spreadsheet.isEmpty(): spreadsheet.writeheader()                
    spreadsheet.add_line_from_dict(outdata)

def task_write_postprocessor_report(conf:type_conf, sample:type_sample)-> None:
        # This does nothing unless the class reimplements the empty standard def.
        sample.write_postprocessor_report(conf)

# MAIN PROCESSOR
class jkm_post():
    def __init__(self):
        # The ext instance contains event functions that are called by main() does a task.
        # This allows external sources like a GUI to track the progress of jkm-post.main()
        self.ext = None
        self.fsobserver = None # A watchdog file system observer
        self.urlqueue = queue.Queue() # a FIFO queue of urls that are (hopefully) usable for building Sample objects
        self.threadpool = None # A worker thread pool ... set in main() !
        self.spreadsheet = None # a Spreadsheet obsect
    # ----------------- Verify setup --------------------------------
    def verify_conf(self:Self, conf:type_conf)-> None:
        try: # Configuration verification
            conf.verify( must_have = ["postprocessor", "task", "data","meta","spreadsheet",
                                      ["data","main_data_directory"],
                                      ["data","datatype_to_load"],
                                      ["data","sample_pattern"],
                                      ["postprocessor","monitor"],
                                      ["postprocessor","process_existing"],
                                      ["postprocessor","sleep_after_new_sample_detected"],
                                        ],
                         should_have = []
                        )
            if conf.has_section("barcodes"):
                log.debug(f'Using QR code decoder { conf.get( "barcodes", "barcodepackage") }')
            if not conf.basepath.exists(): raise jkm.errors.ConfigError(f"Resource base {conf.basepath} does not exist.")
        except jkm.errors.ConfigWarning: # ConfigError is way worse and is handled at the end
            pass # Exception does its own logging  
    # ----------------- Initialize state  -----------------------------
    def init_logging(self:Self,logging_level_file:int, logging_level_stream:int) -> logging.Logger:
        log = jkm.log.setup_logging(jkm.meta.name, logging_level_file, logging_level_stream, ext = self.ext)
        jkm.configfile.log = log    
        jkm.tools.log = log
        jkm.ocr.log = log 
        jkm.sample.log = log
        jkm.samplemetadata.log = log
        jkm.ai.log = log
        jkm.barcodes.log = log
        return log
        
    def init_spreadsheet(self:Self,conf:type_conf) -> type_spreadsheet|None:
        spreadsheetpath = ""
        try: 
            spreadsheetpath = Path(conf.get("spreadsheet","filename") ) 
            if  BACKUP_DATATABLE:  
                timestr = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
                backup_path = spreadsheetpath.with_stem( spreadsheetpath.stem + "_" + timestr )
                # TODO: check return 
                successQ = jkm.tools.safecopy(spreadsheetpath, backup_path) 
            sheetformat = conf.get("spreadsheet","format") 
            if sheetformat.lower() != "csv": 
                log.warning("Unknown ") 
            self.spreadsheet = jkm.spreadsheet.SpreadsheetCSV(spreadsheetpath)
            log.debug(f"Tabular output is appended to file {spreadsheetpath}")
        except IOError as msg: 
            log.critical(f"Error in opening file {spreadsheetpath} for output:{msg}")
            self.spreadsheet = None
        return self.spreadsheet

    def init_AI_auth(self:Self,conf:type_conf) -> None:
        conf.verify( must_have = ["ai", ["ai","auth_type"] ] )
        auth_type = conf.get("ai", "auth_type") # Must exist if we want AI
        log.debug(f"AI authentication method: {auth_type}")
        if auth_type == 'APIKEY':
            conf.verify( must_have = [["ai","APIkeyfile"]] )
            APIPATH = Path(conf.get("ai","APIkeyfile"))
            conf.APIKEY = jkm.ai.load_apikey(APIPATH) # HACK, FIND A BETTER WAY TO PASS THIS
            log.debug(f"Reading API key from {APIPATH}")
            log.debug(f"AI prompt set to \'{conf.get('ai','prompt')}\'")
        elif auth_type == "CLOUD_OAUTH":
            conf.verify( must_have = [["ai","google_project_id"], ["ai","google_location"],
                                      ["ai","app_token_path"], ["ai","tmp_token_path"],
                                      ] )
        elif auth_type == "LOCAL_OAUTH":
            conf.verify( must_have = [["ai","google_project_id"], ["ai","google_location"],
                                      ] )
        else:
            raise jkm.errors.AIError(f"Unknown AI authentication method {auth_type}")                
    # ----------------- A meta-task ------------------------
    def task_edit_images(self:Self, conf:type_conf, sample:type_sample) -> None:
        # ROTATE IMAGES ?
        if conf.getb( "task", "image", "rotate_images"):
            log.debug(f"Rotating image {sample.name}")
            degrees = conf.geti( "task", "image", "rotate", "degrees")    
            task_rotate(sample, degrees, [0, 90, 180, 270])# non-zero value    
            # SAVE ROTATED (NOT IMPLEMENTED)
            # goes here
        else: log.debug(f"{sample.name}: No rotation performed.")
        if conf.getb( "task", "image", "crop_images"):
            for n in conf.getlist( "task", "image", "crop"):
                params = conf.getdict( "task", "image", "crop", n )
                task_crop(sample, params)
        else: log.debug(f"{sample.name}: No crop performed.")

    # ----------------- Process a single event ------------------------
    def processSingleEvent(self:Self, sourceurl:type_url, conf:type_conf, spreadsheet:type_spreadsheet) -> int:
        # Variables to hold extracted data
        # Potential exceptions: jkm.errors.FileLoadingError
        allbarcodes = []
        # If local, checks that it the path exists
        # jkm.tools.as_existing_path( sourceurl ) # Raises an FileLoadingError on failure
                        
        # Try to recognise input file/directory format
        sample_format = conf.get("data", "datatype_to_load")        
        sample_class = get_sample_class( sample_format.lower() )
        if sample_class in (jkm.sample.LuomusInsectLineSample,
                            jkm.sample.LuomusPlantLineSample,
                            jkm.sample.DirectorySample,
                            ): 
            jkm.tools.as_existing_path( sourceurl )  # FileLoadingError on failure
            sample = sample_class.from_directory(sourceurl, conf)
        elif sample_class in (jkm.sample.SingleImageSample,
                              jkm.sample.FileRowSample):
            sample = sample_class.from_url(sourceurl, conf)
        # get_sample_class(sformat) should already block unknown sample types:   
        else:
            raise jkm.errors.FileLoadingError(f"Unknown sample type {sample_format}")
            
##        # MAIN POSTPROCESSOR STARTS HERE
        if sample: log.info(f"New sample found, initial name {sample.name}")
        if self.ext: self.ext.event_new_sample(sample)

        # IMAGE EDITING        
        edit_images = conf.getb( "task", "image_editing_tasks")
        # This meta-function does its own logging etc
        if edit_images:
            self.task_edit_images(conf, sample) 
        
        # FIND BARCODES ?
        if conf.getb( "task", "read_barcodes"):
            allbarcodes += task_read_barcodes(conf,sample)
            if self.ext: self.ext.event_barcode_detection(sample)
        else: log.debug(f"{sample.name}: No barcode extraction.")
                    
        # FOR FURTHER PROCESSING, CHECK IF IDENTIFIER LIST CONTAINS A SINGLE VALID IDENTIFIER
        # In case sample does already have a known identifier, append to to the list
        if sample.identifier: allbarcodes.append(sample.identifier)
        sampleids = jkm.tools.unique(allbarcodes)
        if len(sampleids) == 0:
            log.warning(f"{sample.name}:No usable identifiers found")
        elif len(sampleids) > 1:
            log.warning(f"{sample.name}:Several  different identifiers for the sample in barcodes/OCR/sample metadata")
        else:
            sample.identifier =  sampleids[0] # Sets also sample.shortidentifier
            if self.ext: self.ext.event_single_sample_id(sample)
        
        # FIND TEXT ARES ?
        if conf.getb( "task", "find_text_areas"):
            textareas = task_get_text_areas(conf, sample)
            if self.ext: self.ext.event_textareas(sample)
        else:
            textareas = []
            log.debug(f"{sample.name}: No text area recognition.")

        # PERFORM Classic OCR ?
        if conf.getb( "task", "ocr"):
            task_OCR(conf, sample)
            if self.ext: self.ext.event_OCRtext(sample)
        else: log.debug(f"{sample.name}: No OCR.")

        # AI-BASED TEXT EXTRACTION ?
        if conf.getb( "task", "ai_label_text_extraction"):
            airesult = task_AI_label_data_extraction(conf, sample)
            if airesult: log.info(f'AI label analysis results was \n"{airesult.to_prettyprint()}\n"\n')
            else: log.warning(f'AI label analysis results was empty.\n') # Shouldn't happen
            if self.ext: self.ext.event_ai_labeltext(sample)
        else:
            airesult = None
            log.debug(f"{sample.name}: No AI label data extraction.")

        # SUBMIT alltext to COMPONENT ANALYSIS (splitting raw text into locality, collector etc)?
#       if conf.getb( "task", "ocr") and
#          conf.getb( "task", "ocr_analysis") and
#          sample.results.ocrtext:
#         **** Not currently implemented. ****
#       Also, the current AI label data extractor does already do this. 
#       A large task and very content-

        # RENAME DIRECTORIES (this may need to stay above file renaming)  
        if sample.shortidentifier \
                  and  conf.getb( "task", "directories_rename_by_barcode_id") \
                  and sample.supports_rename_directories:
            sleep_before = conf.geti("postprocessor", "sleep_before_renaming", default=0)
            task_rename_directories(conf, sample, sleep_before)
            if self.ext: self.ext.event_renamed_directories(sample)
        else: log.debug(f"{sample.name}: No directory rename.")

        # RENAME FILES
        # Current implementation renames only the original image files as per the configuration file
        if sample.shortidentifier \
                        and conf.getb( "task", "files_rename_by_barcode_id", default=False) \
                        and sample.supports_rename_files:
            task_add_prefix_to_imagefiles(sample)
            if self.ext: self.ext.event_renamed_image_files(sample)
        else: log.debug(f"{sample.name}: No file(s) rename.")

        # FINALLY, WRITE RESULTS TO FILES
        # Store interpreted data in a spreadsheet file 
        if self.spreadsheet and conf.getb( "task", "ai_label_text_extraction"):
            # Check if we want to store raw/all output from the AI (it can be loooong)
            write_raw_output= conf.getb( "spreadsheet", "write_raw_output", default = True)
            task_write_spreadsheet(self.spreadsheet, airesult,sample.identifier, write_raw_output)
            log.debug(f"{sample.name}: Adding row to spreadsheet done.")
        else: log.debug(f"{sample.name}: No data export to a spreadsheet.")

        # Create backup scaled-down images for review:
        if conf.getb( "task", "save_images"):
            image_backup_path = conf.getpath( "task", "saveimages","path")
            max_size = conf.geti( "task", "saveimages","max_size")
            task_backup_images(sample, image_backup_path, max_size)
            log.debug(f"Saved review images to {image_backup_path}.")
            
        
        # Write sample metadata to a JSON Metadata file (should this be before renaming?)
        if conf.getb( "task", "save_JSON", default=False):
            sample.writeMetaJSON()
        else: log.debug(f"{sample.name}: No JSON metadata file created.")

        # Write a sample (and sample type) specific postprocessor report file (or files)
        if conf.getb( "task", "write_postprocessor_report_file", default=False):
            log.debug(f"{sample.name}: Postprocessor report file created for sample.")
            task_write_postprocessor_report(conf, sample)
        else: log.debug(f"{sample.name}: No postprocessor report file created for sample.")

        log.info(f"Postprocessing sample {sample.name} ready.")
        if self.ext: self.ext.event_sample_done(sample, processor.SUCCESS)
        return processor.SUCCESS
# ----------------- main worker function, called in a new thread created when a sample arrival event is noticed ------------------------
    def processSampleEvents(self:Self,queue:queue.Queue, conf:type_conf, sleep_s:int, spreadsheet:type_spreadsheet) -> None:
        while True:
            next_input = queue.get()
            if next_input is None: break
            time.sleep(sleep_s) # Wait for all data to arrive
            try:
                log.debug(f"Processing data from {next_input}" )
                successQ = self.processSingleEvent( next_input, conf, self.spreadsheet )        
            except (jkm.errors.FileLoadingError,
                    jkm.errors.FileSavingError) as msg:
                log.error(msg)
                successQ = processor.FAIL_IGNORE                
            if successQ is processor.FAIL_RETRY: queue.put( next_input ) # retry from start
            elif successQ is processor.FAIL_IGNORE: pass 
            elif successQ is processor.SUCCESS: pass 
            log.info(f"Sample events in process queue: {queue.qsize()}\n\n") # Queue still contains this item, thus -1 in the number reported               

# ----------------- only function others should call! -----------------------------
    def main(self:Self,
             logging_level_file:int = logging.INFO,
             logging_level_stream:int= logging.INFO,
             threadpool = myThreadPool(),
             ext:type_external|None=None ):
        """jkm_post main function.

            Arguments:
            logging_level_file - log file logging level (typically logging.DEBUG or logging.INFO)
            logging_level_stream - console/external logging level.
            threadpool - a thread pool. GUI implementations should provide a GUI-save version
            ext - a even handler object. 
            """
        try:
            global log
            self.ext = ext # hooks for an external event handler (like a GUI)
            self.threadpool = threadpool
            # Set loggers in all modules
            log = self.init_logging(logging_level_file, logging_level_stream)
            log.info(f"STARTING NEW SESSION of {jkm.meta.nameversion}") # We having logging set up
            # Read config file name from sys.argv and parse the file
            (conf, _DEBUG) = jkm.configfile.load(jkm.meta.name)
            if _DEBUG: # re-init logging
                log = self.init_logging(logging.DEBUG, logging.DEBUG)
                
            self.verify_conf(conf) # Check that config has basic data needed to run
            datafile_patterns = conf.getlist("data", "sample_pattern")
            # Set some behaviour-controlling variables
            jkm.ai.TESTING_BYPASS_AI_CALL = conf.getb("internal","bypass_AI", default = False)
            if jkm.ai.TESTING_BYPASS_AI_CALL:
                log.warning("*******AI BYPASS TESTING MODE IS ON*******")
            N_WORKER_THREADS = conf.geti("internal","n_threads", default = 17)
            if conf.getb("task", "labeldata_to_CSV", default = False):
                self.spreadsheet = self.init_spreadsheet(conf)

            if conf.getb("task", "ai_label_text_extraction", default = False):
                # Reads keys if needed, verifies conf for chosen method. Raises jkm.errors.AIError on failure
                self.init_AI_auth(conf) 

            # Should be process existing data ?
            if conf.getb("postprocessor", "process_existing"):            
                for fn in find_existing_events(conf):
                    self.urlqueue.put(fn)
                log.info(f"Approximate number of sample events to process at launch is {self.urlqueue.qsize()}")
            
            # Create worker threads for handlinf Sample processing requests
            wait_after_sample_s = conf.getf("postprocessor", "sleep_after_new_sample_detected")
            for i in range(N_WORKER_THREADS):
                self.threadpool.newthread( target = self.processSampleEvents,
                                      args = (self.urlqueue,conf, wait_after_sample_s, self.spreadsheet) )
            #Start loops looking for data to process and processing it
            # Wait period from file detection to file processing
            # Allows for enough time for transfer of a file(s)  to be completed
            if not conf.getb( "postprocessor", "monitor"):
                log.debug(f"NOT MONITORING - will process target directory once: {str(conf.basepath)} ")
            else:   
                # Monitor file system --- will also process any data inserted in the queue before this point!
                log.debug(f"MONITORING DIRECTORY: {str(conf.basepath)}.")
                # Start a filesystem watchdog thread watching for NEW .metadata files
                event_handler = myFileEventHandler(self.urlqueue, patterns=datafile_patterns) # HERE
                self.fsobserver = watchdog.observers.Observer() 
                self.fsobserver.schedule(event_handler, str(conf.basepath), recursive=True)
                self.fsobserver.start()
                # wait: fsobserver sends handling requests to threadpool threads from the queue
                # note that  processSampleEvents has a sleep to stop the process from eating all resources.
                try: 
                    while True:
                        time.sleep(1)
                        log.debug(f"Queue size is currently {self.urlqueue.qsize()}" )
                except KeyboardInterrupt:
                    pass # Fall through to the end of the script
        # Check for fatal error states:
        except UnicodeEncodeError as msg:
            msg = f"Unicode encoding error: '{msg}'"
            log.critical(msg)
            if self.ext: self.ext.event_failure( msg )
        except jkm.errors.JKError as msg:
            # jkm.errors.ConfigError gets caught here
            msg = f"Execution failed with error message '{msg}'"
            log.critical(msg)
            if self.ext: self.ext.event_failure( msg )
#        except Exception as msg:
#            # Forward all errors to logger before quitting, if we are not writing at DEBUG level
#            if logging_level_stream != logging.DEBUG:
#                logginglog.error(f"Other error: {msg}")
        # Cleanup before closing: close all threading processes etc.
        self.stop()

    def stop(self) -> None:
        """End of run tasks. Stop gracefully."""
        if self.fsobserver:
            self.fsobserver.stop() # Stop the watchdog file system observer
            self.fsobserver.join() # block until all tasks are done
            self.fsobserver = None
        # Signal end-of-life to worker threads
        if self.threadpool:
            end_of_life_signal = None # Standard for queue.Queue()        
            for i in range(self.threadpool.activethreadcount):
                self.urlqueue.put( end_of_life_signal )
            # Wait for each worker thread to end properly
            self.threadpool.join()
            self.threadpool= None
        log.debug("Ending session, closing spreadsheet file.")
        if self.spreadsheet:
            self.spreadsheet.close() # Close tries to save, but lets we certain.
        if self.ext: self.ext.event_exit(f"{jkm.meta.nameversion} closing down") # Just in case, do before closing logs
        log.info("Ending session, closing log files.")
        logging.shutdown()
        
