# -*- coding: utf-8 -*-
""" Class usage: create a jkm_post object and call its main() function. """
#
# Check: Watchdog in licences using the Apache License, Version 2.0 
# ADD ATEXIT CALL TO CLOSE LOG FILES ON CRASH OR OTHER CLEAN ERROR HANDLING
import logging
log = logging.getLogger() # Overwrite if needed

# Standard python modules
import time,  logging,  threading, sys, configparser, queue
from datetime import datetime
from pathlib import Path
# non-stdlib modules
import watchdog, watchdog.events
# app-specific modules
import jkm.configfile,  jkm.sample,  jkm.tools
import jkm.spreadsheet,  jkm.ai
import jkm.meta, jkm.errors,  jkm.barcodes
import jkm.external as ext
# import jkm.ocr_analysis

# CONSTANTS
_BACKUP_DATATABLE = True
_num_worker_threads = 1 # BETTER KEEP THIS AT 1: AI PROCESSES DO NOT SEEM TO LIKE CONCURRENT CALLS
_AI_AUTH_TYPES = ("APIKEY", "CLOUD_OAUTH", "LOCAL_OAUTH")
class processor:
    SUCCESS = 0
    FAIL_IGNORE = 1
    FAIL_RETRY = 2
#------------------ MISC TOOLS  -------------------
# Default threadpool, using Python threading module.
class myThreadPool():
    @property
    def activethreadcount(self): return len(self.threads) 
    def __init__(self):
        self.threads = []
    def newthread(self, target, args= ()):
        t = threading.Thread(target=target, args=args)
        t.start()
        self.threads.append(t)            
    def join(self):
        for t in self.threads: t.join()
        self.threads = []

# MAP sample format string from config to a sample class
# NEW CLASS DEVELOPERS: ADD YOUR CLASS HERE
def get_sample_class(sample_format_str):
    str2class = {
        "mzh_insectline" : jkm.sample.LuomusInsectLineSample,
        "mzh_plantline":  jkm.sample.LuomusPlantLineSample,
        "singlefile":  jkm.sample.SingleImageSample,
        "imagedir":  jkm.sample.ImageDirectorySample,
        }
    try:
        return str2class[ sample_format_str.lower() ]
    except KeyError:
        raise jkm.errors.FileLoadingError(f"Unknown sample file/directory format {sample_format}, skippping to next.")
    
class myFileEventHandler(watchdog.events.PatternMatchingEventHandler):
    _lastinsert = None
    def __init__(self, queue, **kwargs): 
        self.queue = queue
        super().__init__(**kwargs)
    def on_created(self, event): 
        if event.src_path != self._lastinsert: self.queue.put(event.src_path)
        else: log.debug(f"Prevented double insertion of {event.src_path} into the queue")
        self._lastinsert = event.src_path        

def find_existing_events(conf):
            datafile_patterns = conf.getlist("data", "recognize_by_filename_pattern")        
            # Find list of file names matching a pattern and put them into the queue
            sample_format = conf.get("data", "datatype_to_load")        
            sample_class = get_sample_class( sample_format.lower() )
            found = sample_class.find_samples(conf.basepath,datafile_patterns)          
            return found
        
#------------------ SINGLE TASKS -------------------
def task_add_prefix_to_imagefiles(sample):
    try:
        new_name_prefix = sample.shortidentifier
        sample.add_prefix_to_imagefiles(new_name_prefix, prefix_separator= "_")
    except (jkm.errors.JKError, FileNotFoundError) as msg:
        log.error(f"{sample.name}: Renaming files failed: {msg}.")                

def task_OCR(conf, sample):
    alltext = ""
    ocr_command = conf.get("ocr", "ocr_command")
    for image in sample.imagelist:
        if not image.has_labels : continue # Skip pure specimen images
        labeltxt = image.ocr(ocr_command) # Default ocr uses fragments created above
        alltext += " " + labeltxt
    sample.meta.addlog("Combined OCR result for all images",alltext,  log_add_hdr= sample.name, lvl = logging.DEBUG)
    sample.results.ocrtext = alltext
    return alltext

def task_read_barcodes(conf,sample):
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

def task_get_text_areas(conf, sample):
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

def task_AI_label_data_extraction(conf, sample):
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
        else: pass # Should never happen as ai_auth_type is verified to havce a valid value at this point
        myai.model = conf.getstr('ai','model')
        myai.prompt = conf.getstr('ai','prompt')
        imagepaths = [x.filename for x in sample.imagelist if x.has_labels]
        image_max_dim = conf.geti("ai", "max_image_dim", default=0)
        airesult = myai.query_images( imagepaths,  image_max_dim = image_max_dim)
        if myai: myai.close()
        # airesult can contain almost anything, possibly including non-valid UTF8. Should sanitize better.
        log.debug(f"{sample.name}:AI call for data extraction returned {str(airesult)}")
        outfn = conf.get("ai","properties_filename")
        if outfn: # If a properties_filename was defined
            outpath = sample.datapath / outfn
            with outpath.open("w") as f: f.write(airesult.to_json())                                                        
        else: log.debug(f"{sample.name}:No AI properties file generation requested in config file")
    except (IOError,  jkm.errors.AIError) as msg:
        log.warning(f"{sample.name}: AI Error '{msg}'.")
        airesult = None
    sample.results.labeltext_ai1 = airesult
    return airesult
    
def task_rename_directories(conf, sample):
    # Tries a few times in case directory renaming is blocked by other processes
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
            attempt_current += 1
            time.sleep(wait_time)

def task_rotate(sample, degrees):
    assert(degrees in [0,90,180,270])
    for image in sample.imagelist:
        log.debug(f"{sample.name}: Rotating image {image.name}")
        image.rotate(rot)

def task_write_spreadsheet(spreadsheet, airesult, barcode_identifier=None, write_raw_output=True):
    # We handle spreadsheet opening here because we do not know possible header fields at script start time!
    raw = "raw"
    if barcode_identifier: outdata = {"barcode_ID": barcode_identifier or ""}
    else: outdata = {}
    if airesult:
        outdata.update(airesult.to_dict() )
        outdata.update( {raw: airesult.raw} )
    if (not write_raw_output) and (raw in outdata):
        del outdata[raw]
    if not spreadsheet.isOpen(): 
        spreadsheet.open(fieldnames = outdata )
        if spreadsheet.isEmpty(): spreadsheet.writeheader()                
    spreadsheet.add_line_from_dict(outdata)

def task_write_postprocessor_report(conf, sample):
        # This does nothing unless the class reimplements the empty standard def.
        sample.write_postprocessor_report(conf)

# MAIN PROCESSOR
class jkm_post():
    def __init__(self):
        # The ext instance contains event functions that are called by main() does a task.
        # This allows external sources like a GUI to track the progress of jkm-post.main()
        self.ext = None
        self.fsobserver = None # A watchdog file system observer
        self.filequeue = queue.Queue() # a FIFO queue of trigger file names
        self.threadpool = None # A worker thread pool ... set in main() !
        self.spreadsheet = None # a Spreadsheet obsect
    # ----------------- Verify setup --------------------------------
    def verify_conf(self, conf):
        try: # Configuration verification
            conf.verify( must_have = ["postprocessor", "tasks", "data","meta","spreadsheet",
                                      ["data","main_data_directory"],
                                      ["data","datatype_to_load"],
                                      ["data","recognize_by_filename_pattern"],
                                      ["postprocessor","monitor"],
                                      ["postprocessor","process_existing"],
                                      ["postprocessor","sleep_after_new_sample_detected"],
                                        ],
                         should_have = []
                        )
            if conf.has_section("barcodes"):
                log.debug(f'Using QR code decoder { conf.get( "barcodes", "barcodepackage") }')
            jkm.tools.quit_if_not_exists(conf.basepath)
        except jkm.errors.ConfigWarning: # ConfigError is way worse and is handled at the end
            pass # Exception does its own logging  
    # ----------------- Initialize state  -----------------------------
    def init_logging(self,logging_level_file, logging_level_stream):
        global log  # !!!!
        log = jkm.tools.setup_logging(jkm.meta.name, logging_level_file, logging_level_stream, ext = self.ext)
        jkm.configfile.log = log    
        jkm.tools.log = log
        jkm.ocr.log = log  # IF OCR
        jkm.sample.log = log
        jkm.samplemetadata.log = log
        jkm.ai.log = log
        jkm.barcodes.log = log
        return log
        
    def init_spreadsheet(self,conf): 
        try: 
            spreadsheetpath = Path( conf.get("spreadsheet","filename") ) 
            if  _BACKUP_DATATABLE:  
                timestr = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
                backup_path = spreadsheetpath.with_stem( spreadsheetpath.stem + "_" + timestr ) 
                jkm.tools.backup_file(spreadsheetpath,  backup_path) # TODO: check return 
            sheetformat = conf.get("spreadsheet","format") 
            if sheetformat.lower() != "csv": 
                log.warning("Unknown ") 
            self.spreadsheet = jkm.spreadsheet.SpreadsheetCSV(spreadsheetpath)
            log.debug(f"Tabular output is appended to file {spreadsheetpath}")
        except IOError as msg: 
            log.critical(f"Error in opening file {spreadsheetpath} for output:{msg}")
            self.spreadsheet = None
        return self.spreadsheet

    def init_AI_auth(self,conf):
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

    # ----------------- Process a single event ------------------------
    def processSingleEvent(self,filename, conf, spreadsheet):
        log.debug(f"Processing data file {filename}" )
        # Variables to hold extracted data
        allbarcodes = []
        try:
            # Create a Sample Event
            dirpath= filename.parent
            # Catch some error states
            if not dirpath.is_dir():                
                raise jkm.errors.FileLoadingError(f"Cannot find path {dirpath},  skipping to next sample.")
            if not filename.exists():
                raise jkm.errors.FileLoadingError(f"Could not find file {filename}, skipping.")
            # Try to recognise input file/directory format
            sample_format = conf.get("data", "datatype_to_load")        
            sample_class = get_sample_class( sample_format.lower() )
            if sample_class in (jkm.sample.LuomusInsectLineSample,
                                jkm.sample.LuomusPlantLineSample,
                                jkm.sample.ImageDirectorySample,
                                ): 
                sample = sample_class.from_directory(dirpath, conf)
            elif sample_class in (jkm.sample.SingleImageSample,  ):
                sample = sample_class.from_image_file(filename, conf)
            # get_sample_class(sformat) should already block unknown sample types:   
            else: assert False, "Unknown sample format."
        except jkm.errors.FileLoadingError as msg:
                    log.error(msg)
                    return processor.FAIL_IGNORE
                
        # MAIN POSTPROCESSOR STARTS HERE
        log.info(f"New sample found, initial name {sample.name}")
        if self.ext: self.ext.event_new_sample(sample)

        # ROTATE IMAGES ?
        degrees = conf.geti( "tasks", "rotate_before_processing")
        if degrees: task_rotate(degrees)# non-zero value    
        else: log.debug(f"{sample.name}: No rotation performed.")
        # SAVE ROTATED (NOT IMPLEMENTED)
        
        # FIND BARCODES ?
        if conf.getb( "tasks", "read_barcodes"):
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
        if conf.getb( "tasks", "find_text_areas"):
            textareas = task_get_text_areas(conf, sample)
            if self.ext: self.ext.event_textareas(sample)
        else:
            textareas = []
            log.debug(f"{sample.name}: No text area recognition.")

        # PERFORM Classic OCR ?
        if conf.getb( "tasks", "ocr"):
            task_OCR(conf, sample)
            if self.ext: self.ext.event_OCRtext(sample)
        else: log.debug(f"{sample.name}: No OCR.")

        # AI-BASED TEXT EXTRACTION ?
        if conf.getb( "tasks", "ai_label_text_extraction"):
            airesult = task_AI_label_data_extraction(conf, sample)
            log.info(f'AI label analysis results was "\n{airesult.to_prettyprint()}\n"\n')
            if self.ext: self.ext.event_ai_labeltext(sample)
        else:
            airesult = None
            log.debug(f"{sample.name}: No AI label data extraction.")

        # SUBMIT alltext to COMPONENT ANALYSIS (splitting raw text into locality, collector etc)?
#       if conf.getb( "tasks", "ocr") and
#          conf.getb( "tasks", "ocr_analysis") and
#          sample.results.ocrtext:
#         **** Not currently implemented. ****
#       Also, the current AI label data extractor does already do this. 
#       A large task and very content-

        # RENAME DIRECTORIES (this may need to stay above file renaming)  
        if sample.shortidentifier \
                  and  conf.getb( "tasks", "directories_rename_by_barcode_id") \
                  and sample.supports_rename_directories:
            task_rename_directories(conf, sample)
            if self.ext: self.ext.event_renamed_directories(sample)
        else: log.debug(f"{sample.name}: No directory rename.")

        # RENAME FILES
        # Current implementation renames only the original image files as per the configuration file
        if sample.shortidentifier \
                        and conf.getb( "tasks", "files_rename_by_barcode_id", default=False) \
                        and sample.supports_rename_files:
            task_add_prefix_to_imagefiles(sample)
            if self.ext: self.ext.event_renamed_image_files(sample)
        else: log.debug(f"{sample.name}: No file(s) rename.")

        # FINALLY, WRITE RESULTS TO FILES
        # Store interpreted data in a spreadsheet file 
        if self.spreadsheet and conf.getb( "tasks", "ai_label_text_extraction"):
            # Check if we want to store raw/all output from the AI (it can be loooong)
            write_raw_output= conf.getb( "spreadsheet", "write_raw_output", default = True)
            task_write_spreadsheet(self.spreadsheet, airesult,sample.identifier, write_raw_output)
            log.debug(f"{sample.name}: ...table data adding done")
        else: log.debug(f"{sample.name}: No data export to a spreadsheet.")

        # Write sample metadata to a JSON Metadata file (should this be before renaming?)
        if conf.getb( "tasks", "save_JSON", default=False):
            sample.writeMetaJSON()
        else: log.debug(f"{sample.name}: No JSON metadata file created.")

        # Write a sample (and sample type) specific postprocessor report file (or files)
        if conf.getb( "tasks", "write_postprocessor_report_file", default=False):
            log.debug(f"{sample.name}: Postprocessor report file created for sample.")
            task_write_postprocessor_report(conf, sample)
        else: log.debug(f"{sample.name}: No postprocessor report file created for sample.")

        log.info(f"Postprocessing sample {sample.name} ready.")
        if self.ext: self.ext.event_sample_done(sample, processor.SUCCESS)
        return processor.SUCCESS

# ----------------- main worker function, called in a new thread created when a sample arrival event is noticed ------------------------
    def processSampleEvents(self,queue, conf, sleep_s, spreadsheet):
        while True:
            # Input queue item = name of file found by the directory watcher tool
            next_input = queue.get()
            if next_input is None: break
            filename = Path( next_input )
            time.sleep(sleep_s) # Wait for all data to arrive
            successQ = self.processSingleEvent( filename, conf, self.spreadsheet )        
            if successQ is processor.FAIL_RETRY: queue.put( next_input ) # retry from start
            elif successQ is processor.FAIL_IGNORE: queue.done() 
            elif successQ is processor.SUCCESS: pass # Do nothing
#            if self.ext: self.ext.event_sample_done(sample, processor.SUCCESS) # ... but we do NOT know the sample here, at it is not returned. TODO
            #DONE
            log.info(f"Sample events in process queue: {queue.qsize()}\n\n") # Queue still contains this item, thus -1 in the number reported               

# ----------------- only function others should call! -----------------------------
    def main(self,logging_level_file = logging.INFO, logging_level_stream = logging.INFO,threadpool = myThreadPool(), ext=None ):
        """jkm_post main function.

            Arguments:
            logging_level_file - 
            logging_level_stream -  
            threadpool - a thread pool. GUI implementations should provide a GUI-save version
            ext - a even handler object. 
            """
        self.ext = ext # hooks for an external event handler (like a GUI)
        self.threadpool = threadpool
        # Set loggers in all modules
        log = self.init_logging(logging_level_file, logging_level_stream)
        log.info(f"STARTING NEW SESSION of {jkm.meta.nameversion}") # We having logging set up
        # Read config file name from sys.argv and parse the file
        try: 
            conf = jkm.configfile.load(jkm.meta.name)
            self.verify_conf(conf) # Check that config has basic data needed to run
            datafile_patterns = conf.getlist("data", "recognize_by_filename_pattern")

            if conf.getb("postprocessor", "process_existing"):            
                for fn in find_existing_events(conf):
                    self.filequeue.put(fn)
                log.info(f"Approximate number of sample events to process at launch is {self.filequeue.qsize()}")
            
            if conf.getb("tasks", "labeldata_to_CSV", default = False):
                self.spreadsheet = self.init_spreadsheet(conf)

            if conf.getb("tasks", "ai_label_text_extraction", default = False):
                # Reads keys if needed, verifies conf for chosen method. Raises jkm.errors.AIError on failure
                self.init_AI_auth(conf) 

            # Create worker threads for handlinf Sample processing requests
            wait_after_sample_s = conf.getf("postprocessor", "sleep_after_new_sample_detected")
            for i in range(_num_worker_threads):
                self.threadpool.newthread( target = self.processSampleEvents,
                                      args = (self.filequeue,conf, wait_after_sample_s, self.spreadsheet) )
            #Start loops looking for data to process and processing it
            # Wait period from file detection to file processing
            # Allows for enough time for transfer of a file(s)  to be completed
            if not conf.getb( "postprocessor", "monitor"):
                log.debug(f"NOT MONITORING - will process target directory once: {str(conf.basepath)} ")
            else:   
                # Monitor file system --- will also process any data inserted in the queue before this point!
                log.debug(f"MONITORING DIRECTORY: {str(conf.basepath)}.")
                # Start a filesystem watchdog thread watching for NEW .metadata files
                event_handler = myFileEventHandler(self.filequeue, patterns=datafile_patterns) # HERE
                self.fsobserver = watchdog.observers.Observer() 
                self.fsobserver.schedule(event_handler, str(conf.basepath), recursive=True)
                self.fsobserver.start()
                # wait: fsobserver sends handling requests to threadpool threads from the queue
                # note that  processSampleEvents has a sleep to stop the process from eating all resources.
                try: 
                    while True:
                        time.sleep(2)
                        log.debug(f"Queue size is currently {self.filequeue.qsize()}" )
                except KeyboardInterrupt:
                    pass # Fall through to the end of the script
        # Check for fatal error states:
        except UnicodeEncodeError as msg:
            msg = f"Unicode encoding error: '{msg}'"
            log.critical(msg)
            if ext: ext.event_failure( msg )
        except jkm.errors.JKError as msg:
            # jkm.errors.ConfigError gets caught here
            msg = f"Execution failed with error message '{msg}'"
            log.critical(msg)
            if ext: ext.event_failure( msg )
#        except Exception as msg:
#            # Forward all errors to logger before quitting, if we are not writing at DEBUG level
#            if logging_level_stream != logging.DEBUG:
#                logginglog.error(f"Other error: {msg}")
        # Cleanup before closing: close all threading processes etc.
        self.stop()

    def stop(self):
        """End of run tasks. Stop gracefully."""
        if self.fsobserver:
            self.fsobserver.stop() # Stop the watchdog file system observer
            self.fsobserver.join() # block until all tasks are done
            self.fsobserver = None
        log.debug("Ending session, shutting down file system observer.")
        # Signal end-of-life to worker threads
        if self.threadpool:
            end_of_life_signal = None # Standard for queue.Queue()        
            for i in range(self.threadpool.activethreadcount):
                self.filequeue.put( end_of_life_signal )
                log.debug(f"Ending session, worker thread {i+1} closed.")
            # Wait for each worker thread to end properly
            log.info("Ending session, waiting for worker threads to finish.")    
            self.threadpool.join()
            log.info("\tdone.")    
            self.threadpool= None
        log.debug("Ending session, closing spreadsheet file.")
        if self.spreadsheet:
            self.spreadsheet.close() # Close tries to save, but lets we certain.
        if self.ext: ext.event_exit(f"{jkm.meta.nameversion} closing down") # Just in case, do before closing logs
        log.info("Ending session, closing log files.")
        logging.shutdown()
        
