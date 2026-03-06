# -*- coding: utf-8 -*-
# Check: Watchdog in licences using the Apache License, Version 2.0 
# TODO: ADD ATEXIT CALL TO CLOSE LOG FILES ON CRASH

# Set a environment variable to disable problematic CTRL-C handling in 
# some apparently scipy-related Fortran code. Needs to be before scipy
# is imported.
import os
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

import time,  logging,  threading, sys,   configparser
from datetime import datetime
from pathlib import Path
import queue
# non-stdlib modules
from watchdog.observers import Observer
import watchdog.events
# app-specific modules
import jkm.configfile,  jkm.sample,  jkm.tools,  jkm.errors,  jkm.barcodes, jkm.ocr_analysis,  jkm.ai

_DEBUG = True  
_num_worker_threads = 1
_program_name = "jkm-post"
_program_ver = "1.31a" 
_program = f"{_program_name} ({_program_ver})"

_SUCCESS = 0
_FAIL_IGNORE = 1
_FAIL_RETRY = 2

def _UNIQUE(s) :return tuple(set(s))

def quit_if_not_exists(pathname):
    if not pathname.exists():
        log.critical(f"Path {pathname} not found. Quitting.")
        sys.exit()

# Move to Luomus-specific Sample type
def find_samples(dirname,datafile_patterns):
    #This just returns a list of matching file names
    log.debug(f"Finding '{datafile_patterns}' files to process if {dirname}" )
    d = Path(dirname) 
    result = []
    for pat in datafile_patterns: 
        tempr = d.rglob(pat)
        log.debug(f"Looking for pattern {pat} in {dirname}")
        tempr = [x for x in tempr if ( str(x).find("textarea") == -1 )] # Skip files with "textarea" in their name
        result.extend( tempr )
    # Delete duplicate files (hard links to the same file)
    return _UNIQUE(result)


class myFileEventHandler(watchdog.events.PatternMatchingEventHandler):
    _lastinsert = None
    def __init__(self,  *args,  **kwargs): super().__init__(*args,**kwargs)
    def on_created(self, event): 
        if event.src_path != self._lastinsert: q.put(event.src_path)
        else: log.debug(f"Prevented double insertion of {event.src_path} into the queue")
        self._lastinsert = event.src_path        

def path_in_list(p,pathlist):
    for p2 in pathlist: 
        if p.samefile(p2): return True
    return False		

def write_postprocessor_properties_file(sample):
    """Write postprocessor.properties file"""
    try:
            sample.digipropfile.setheader( f"# {datetime.now()}" )
            sample.digipropfile.update("full_barcode_data",sample.identifier or "")
            sample.digipropfile.update("identifier",sample.shortidentifier  or "")
            sample.digipropfile.update("timestamp",sample.original_timestamp())
            if sample.identifier: # Only one identifier-containing barcode was found
                id_OK = sample.verify_identifier()
                if not id_OK: 
                    log.critical(f"{sample.name}: *******\n\n\n\nMALFORMED IDENTIFIER {sample.identifier}*******\n\n\n\n")
                sample.digipropfile.update("URI_format_OK", str(id_OK) )
            sample.digipropfile.update("Q-sharp", "" )
            sample.digipropfile.update("Q-color", "" )
            if conf.getb( "postprocessor", "ocr"): 
                sample.digipropfile.update("OCR_result", alltext.replace("\n"," "))
            propfilepath = sample.datapath /  Path(r"postprocessor.properties") 
            sample.digipropfile.save( sample.datapath /  Path(r"postprocessor.properties") )
    except OSError as msg:
        assert(propfilepath) # Should exist if this exception was triggered
        log.warning( f"Saving a properties file failed with error message: {msg}" )

# ----------------- Process a single event ------------------------
def processSingleEvent(filename, data_out_table):
        log.debug(f"Processing data file {filename}" )
        # Variables to hold extracted data
        alltext = ""
        ocrdata = []
        allbkdata = []
        # Create SampleEvent instances based on (meta)data file(s)
        #Recognise type to load
        sample_format = conf.get("sampleformat", "datatype_to_load")        
        try:
            dirpath= filename.parent
            # Catch some error states
            if not dirpath.is_dir():                
                raise jkm.errors.FileLoadingError(f"Cannot find path {dirpath},  skipping to next sample.")
            if not filename.exists():
                raise jkm.errors.FileLoadingError(f"Could not find file {filename}, skipping.")
            # Try to recognise input file/directory format
            if sample_format.lower() == "mzh_insectline": 
                print("TRYING INSECTLINE")
                sample = jkm.sample.LuomusInsectLineSample.from_directory(dirpath, conf)
            elif sample_format.lower() ==  "mzh_plantline": 
                sample = jkm.sample.LuomusPlantLineSample.from_directory(dirpath, conf)
            elif sample_format.lower() == "singlefile":
                sample = jkm.sample.SingleImageSample.from_image_file(filename, conf, "generic_camera")
            else:
                raise jkm.errors.FileLoadingError(f"Unknown sample file/directory format {sample_format}, skippping to next.")
        except jkm.errors.FileLoadingError as msg:
                log.error(msg)
                q.task_done(); 
                return _FAIL_IGNORE
                
        # MAIN POSTPROCESSOR STARTS HERE
        # TODO: CHECK IF THIS WORKS WITH THE REIMPLEMENTED sample
        log.info(f"Postprocessing sample {sample.name}")
        # ROTATE
        rot = conf.geti( "postprocessor", "rotate_before_processing")
        if rot: # non-zero value
            for image in sample.imagelist:
                log.debug(f"{sample.name}: Rotating image {image.name}")
                image.rotate(rot)
        else: log.debug(f"{sample.name}: No rotation performed.")
        # SAVE ROTATED (NOT IMPLEMENTED)
        
        # FIND BARCODES
        if conf.getb( "postprocessor", "read_barcodes"):
            barcodepackage = conf.get( "barcodes", "barcodepackage").lower()
            for image in sample.imagelist:
                try:
                    # NOTE: the choice of barcose detector tool is hardcoded in jkm/barcodes.py
                    bkdata = image.readbarcodes(barcodepackage)
                    image.meta.addlog("Barcode contents", bkdata, log_add_hdr= sample.name)
                    allbkdata += bkdata
                except jkm.errors.FileLoadingError as msg:
                    log.warning(f"{sample.name}: Barcode detection attempt failed: %s" % msg)
                    continue
        else: log.debug(f"{sample.name}: No barcode extraction.")
                    
        # FIND TEXT ARES
        if conf.getb( "postprocessor", "find_text_areas"):
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                log.debug(f"{sample.name}: Searching for text areas in {image.label} of sample {sample.name}")
                neuralnet = conf.get( "ocr", "EASTfile")
                textareas = image.findtextareas(neuralnet)
                image.meta.addlog("Text areas found", str(textareas),  log_add_hdr= sample.name)
                if conf.getb( "postprocessor", "save_text_area_images"): 
                    image.savetextareas("_textarea_")
        else: log.debug(f"{sample.name}: No text area recognition.")

        # PERFORM OCR
        if conf.getb( "postprocessor", "ocr"):
            ocr_command = conf.get("ocr", "ocr_command")
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                labeltxt = image.ocr(ocr_command) # Default ocr uses fragments created above
                alltext  += " " + labeltxt
#                image.meta.addlog("OCR result for image", labeltxt,lvl=logging.DEBUG)
            sample.meta.addlog("Combined OCR result for all images",alltext,  log_add_hdr= sample.name)
        else: log.debug(f"{sample.name}: No OCR.")

        # AI-based label data extraction
        if conf.getb( "postprocessor", "ai_label_text_extraction"):
            try:
                myai = jkm.ai.geminiAI(APIKEY)
                myai.prompt = PROMPT
                imagepaths = [x.filename for x in sample.imagelist if x.has_labels]
                airesult = myai.query_images( imagepaths )        
                log.info(f"{sample.name}:AI call for data extraction returned {airesult}")
                outfn = conf.get("ai","properties_filename", fallback = False)
                if outfn: # If a properties_filename was defined
                    outpath = sample.datapath / outfn
                    with outpath.open("w") as f: f.write(airesult.to_json())                                                        
                else: log.debug(f"{sample.name}:No AI properties file generation requested in config file")
            except (IOError,  jkm.ai.AIError) as msg:
                log.error(f"Error: {msg}"  )
        else: log.debug(f"{sample.name}: No AI label data extraction.")

        # EXTRACT IDENTIFIERS FROM OCR DATA (NOT IMPLEMENTED)

        # SUBMIT alltext to COMPONENT ANALYSIS
        if conf.getb( "postprocessor", "ocr") and conf.getb( "postprocessor", "ocr_analysis"):
             ocrdata = jkm.ocr_analysis.ocr_analysis_Luomus(alltext)
             log.debug(f"{sample.name}: OCR data parsing output: {ocrdata}")
        else: 
             log.debug(f"{sample.name}: No OCR data parsing attempted.")           
             ocrdata = []

         # FOR FURTHER PROCESSING, CHECK IF IDENTIFIER LIST CONTAINS A SINGLE VALID IDENTIFIER
        # In case sample does already have a known identifier, append to to the list
        if sample.identifier: allbkdata.append(sample.identifier)
        sampleids = _UNIQUE(allbkdata)
        if len(sampleids) == 0:
            log.warning(f"{sample.name}:No usable identifiers found")
        elif len(sampleids) > 1:
            log.warning(f"{sample.name}:Several  different identifiers for the sample in barcodes/OCR/sample metadata")
        else: sample.identifier =  sampleids[0] # Sets also sample.shortidentifier
        
       # Store interpreted data in a table file if 
        if data_out_table: 
#        if sample.identifier and data_out_table:
#            ocrdata.prepend("identifier", sample.identifier) 
            testdata = {"FOO": "Foo1",  "BAR": "bar2"}
            testdata.update( airesult.to_dict() ) 
            testdata["barcode_ID"] = sample.identifier # Should default to None ?
            log.debug(f"{sample.name}: Calling OutputCSV.addline with data: {testdata}")
#            log.debug(f"{sample.name}: data_out_table.fp = {data_out_table.fp}")
            data_out_table.add_line(testdata)
            log.debug(f"{sample.name}: ...table data adding done")
            
        # RENAME DIRECTORIES (this may need to stay above file renaming)  
        # Tries a few times in case directory renaming is blocked by other processes
        if conf.getb( "basic", "directories_rename_by_barcode_id") and sample.identifier:
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
                    log.error(f"{sample.name}: Renaming directory failed: {msg}.")                
                    break # Exit the while loop 
                except FileExistsError as msg:
                    log.error(f"{sample.name}: Renaming directory failed, there is already a directory with this name: {msg}")                
                    break # Exit the while loop 
                except FileNotFoundError as msg:
                    log.error(f"{sample.name}: Renaming directory failed, original directory does not exist anymore: {msg}")                
                    break # Exit the while loop 
                except PermissionError as msg:                
                    log.error(f"No write access: {msg}. \nWill attempt again in {wait_time} seconds {attempt_times-attempt_current} times.")                    
                    attempt_current += 1
                    time.sleep(wait_time)
        else: log.debug(f"{sample.name}: No directory rename.")

        # RENAME FILES
        # Current implementation renames only the original image files as per the configuration file
        if conf.getb( "basic", "files_rename_by_barcode_id") and sample.shortidentifier:
            try:
                sample.rename_all_files(sample.shortidentifier)
            except (jkm.errors.JKError, FileNotFoundError) as msg:
                log.warning(f"{sample.name}: Renaming files failed: {msg}.")                
        else: log.debug(f"{sample.name}: No file(s) rename.")

        # Write records to JSON Metadata file (should this be before renaming?)
        if conf.getb( "basic", "save_JSON"): sample.writeMetaJSON()
        else: log.debug(f"{sample.name}: No JSON metadata file created.")

        # FOR MZH IMAGING LINE SAMPLES
        if conf.get("sampleformat", "datatype_to_load").lower()  in ["mzh_insectline", "mzh_plantline"]:
            write_postprocessor_properties_file(sample)
        else: log.debug(f"{sample.name}: No postprocessor.properties file created.")
        return _SUCCESS
        
# ----------------- main worker function, called in a new thread created when a sample arrival event is noticed ------------------------
def processSampleEvents(conf, sleep_s, data_out_table):
    while True:
        # Input queue = name of file found by the directory watcher tool
        input = q.get()
        if input is None: break
        filename = Path(input)
        time.sleep(sleep_s) # Wait for all data to arrive
        try:
            successQ = processSingleEvent(filename,data_out_table)        
        except (configparser.NoOptionError,  configparser.NoSectionError) as msg:  
            log.critical(f"Loading SETUP file item failed with message: {msg}")
            successQ = _FAIL_IGNORE
        if successQ in [_FAIL_RETRY]: q.put(input) # retry from start 
        elif successQ in [_SUCCESS, _FAIL_IGNORE]: pass # Do nothing
        #DONE
        log.info(f"Sample events in process queue: {q.qsize()}\n\n") # Queue still contains this item, thus -1 in the number reported               

if __name__ == '__main__':
    threads = []
    excel = None
    q = queue.Queue() # a FIFO queue of metafile names
    log = jkm.tools.setup_logging(_program_name, debug = _DEBUG)
    # Set loggers in other modules
    jkm.configfile.log = log    
    jkm.tools.log = log
    jkm.ocr.log = log  # IF OCR
    jkm.sample.log = log
    jkm.metadata.log = log
    jkm.barcodes.log = log
    
    log.info(f"STARTING NEW SESSION of {_program}")
    # Read config file name from sys.argv and parse the file
    try: 
        conf = jkm.configfile.load_configuration(_program_name) 
        # Wait period from file detection to file processing
        # Allows for enough time for transfer of a file(s)  to be completed
        sleep_s_before_reading_file = conf.getf("postprocessor", "sleep_after_new_sample_detected")
        # TODO: get data types to process from config file: event packages (identified by metadata files) or simple image files
        #datatype = conf.get("sampleformat", "datatype_to_load")
        filename_pattern = conf.get("sampleformat", "recognize_by_filename_pattern")        
        datafile_patterns = [filename_pattern]
        if conf.getb("postprocessor", "process_existing"):
            # Find list of file names matching a pattern and put them into the queue
            existingevents = find_samples( conf.basepath,datafile_patterns )
            for fn in existingevents: q.put(fn)
            log.info(f"Approximate number of sample events to process at launch is {q.qsize()}")
        
        if conf.getb("postprocessor", "labeldata_to_CSV"):
            _BACK_UP_DATATABLE = False # Not yet implemented
            try: # Maybe we should open and close a file every time we access it rather than passing an open file around. What appr                
                table_outfile = Path( conf.get("data2table","filename") ) 
                format = conf.get("data2table","format") 
                if format.lower() != "csv": 
                    log.warning 
                # TODO: should check if file exists, create as needed
                fieldnames = ["barcode_ID", "locality", "date",  "collector",  "identifier", "notes"]                
                table_out = jkm.ocr_analysis.OutputCSV( table_outfile,  fieldnames = fieldnames )
                table_out.open()
                log.info(f"Tabular output is appended to file {table_outfile}")
            except IOError as msg: 
                log.error(f"Error in opening file {table_out} for output:{msg}")
                table_out = None
        else: table_out = None
        
        log.debug(f'Using QR code decoder {conf.get( "barcodes", "barcodepackage")}')

        if conf.getb("postprocessor", "ai_label_text_extraction"):            
            APIPATH = Path(conf.get("ai","APIkeyfile"))
            log.debug(f"Reading API key from {APIPATH}")
            APIKEY = jkm.ai.load_apikey(APIPATH)
            log.debug(f"API key is {APIKEY}")
            PROMPT = conf.get("ai","prompt")
            log.debug(f"AI prompt set to '{APIKEY}'")

         #Start loops looking for data to process and processing it
        for i in range(_num_worker_threads):
            t = threading.Thread(target=processSampleEvents,  args=(conf, sleep_s_before_reading_file, table_out))
            t.start()
            threads.append(t)    
        if not conf.getb( "postprocessor", "monitor"):
            log.debug("NOT MONITORING, JUST ONE PASSTHROUGH")
    #        q.join() # block until all tasks are done
        else:        
            log.debug("MONITORING DIRECTORY")
            # Start a filesystem watchdog thread watching for NEW .metadata files
            event_handler = myFileEventHandler(patterns=datafile_patterns) 
            observer = Observer()
            quit_if_not_exists(conf.basepath)
            observer.schedule(event_handler, str(conf.basepath), recursive=True)
            observer.start()
            # Process data from queue while waiting
            try: 
                while True:
                    time.sleep(2)
                    log.debug(f"Queue size is currently {q.qsize()}" )
            except KeyboardInterrupt: # TODO: Add other end-of-life sources
                observer.stop()
                # Wait for other threads to stop 
            observer.join() # block until all tasks are done

        log.info("Ending session, waiting for worker threads to finish.")    
        for i in range(_num_worker_threads): q.put(None) # Signal end-of-life to worker threads
        for t in threads: t.join()   # Wait for each worker thread to end properly
        log.info("Ending session, closing log files.")
        if table_out: table_out.save()
    except jkm.errors.JKError as msg:
        log.critical(f'Execution failed with error message "{msg}"')
    except (configparser.NoOptionError,  configparser.NoSectionError) as msg:  
        log.critical(f"Loading SETUP file item failed with message: {msg}")
    logging.shutdown()
