# Check: Watchdog in licences using the Apache License, Version 2.0 
# TODO: ADD ATEXIT CALL TO CLOSE LOG FILES ON CRASH
import time,  logging,  threading
from datetime import datetime
from pathlib import Path
import queue
# non-stdlib modules
from watchdog.observers import Observer
import watchdog.events
# app-specific modules
import jkm.configfile,  jkm.sample,  jkm.tools,  jkm.errors,  jkm.barcodes, jkm.ocr_analysis

_debug = True    
_num_worker_threads = 4
_program_name = "jkm-post"
_program_ver = "1.3a" 
_program = f"{_program_name} ({_program_ver})"

def _UNIQUE(s) :return list(set(s))

# Move to Luomus-specific Sample type
def find_samples(dirname,datafile_patterns):
    log.debug("Finding files to process" )
    d = Path(dirname)
    res = []
    for pat in datafile_patterns: 
        tempr = d.rglob(pat)
        log.debug(f"Looking for pattern {pat} in {dirname}")
        tempr = [x for x in tempr if ( str(x).find("textarea") == -1 )] # Skip files with "textarea" in their name
        res.extend( tempr )
    # Delete duplicate files (hard links to the same file)
#    r2 = []
#    for x in res:
#        if not path_in_list(x,r2): r2.append(x)
    return res

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
    
# ----------------- main worker function ------------------------
def processSampleEvents(conf, sleep_s, data_out_table):
    while True:
        # Input queue = name of file found by the directory watcher tool
        input = q.get()
        if input is None: break
        filename = Path(input)
        time.sleep(sleep_s) # Wait for all data to arrive
        if not filename.exists():  #" File may aleady have been deleted, renamed etc.
            log.warning(f"Could not find file {filename}, skipping")
            q.task_done()
            continue
        log.debug(f"Processing data file {filename}" )
        # Create SampleEvent instances based on (meta)data file(s)
        #Recognise type to load
        sample_format = conf.get("sampleformat", "datatype_to_load")
        try:
            if sample_format.lower() in ["mzh_insectline", "mzh_plantline"]: 
                dirpath= filename.parent
                if not dirpath.is_dir():
                    log.warning(f"Cannot find path {dirpath},  skipping to next sample")
                    continue
                sample = jkm.sample.MZHLineSample.from_directory(dirpath, conf)
            elif sample_format.lower() == "singlefile":                
                sample = jkm.sample.SingleImageSample.from_image_file(filename, conf, "generic_camera")
            else:
#                sample = jkm.sample.SampleEvent.fromJSONfile(filename)
                raise jkm.errors.FileLoadingError(f"Unknown sample file/directory format {sample_format}")
                q.task_done(); continue
        except jkm.errors.FileLoadingError:
                q.task_done(); continue
                
        # MAIN POSTPROCESSOR STARTS HERE
        # TODO: CHECK IF THIS WORKS WITH THE REIMPLEMENTED sample
        log.info(f"Postprocessing sample {sample.name}")
        # ROTATE
        rot = conf.geti( "postprocessor", "rotate_before_processing")
        if rot: # non-zero value
            for image in sample.imagelist:
                log.debug(f"{sample.name}: Rotating image {image.name}")
                image.rotate(rot)
        # SAVE ROTATED (NOT IMPLEMENTED)
        
        # FIND BARCODES
        allbkdata = []
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
                    
        # FIND TEXT ARES
        if conf.getb( "postprocessor", "find_text_areas"):
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                log.debug(f"Searching for text areas in {image.label} of sample {sample.name}")
                neuralnet = conf.get( "ocr", "EASTfile")
                textareas = image.findtextareas(neuralnet)
                image.meta.addlog("Text areas found", str(textareas),  log_add_hdr= sample.name)
                if conf.getb( "postprocessor", "save_text_area_images"): 
                    image.savetextareas("_textarea_")

        # PERFORM OCR
        alltext = ""
        if conf.getb( "postprocessor", "ocr"):
            ocr_command = conf.get("ocr", "ocr_command")
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                labeltxt = image.ocr(ocr_command) # Default ocr uses fragments created above
                alltext  += " " + labeltxt
#                image.meta.addlog("OCR result for image", labeltxt,lvl=logging.DEBUG)
            sample.meta.addlog("Combined OCR result for all images",alltext,  log_add_hdr= sample.name)

        # EXTRACT IDENTIFIERS FROM OCR DATA (NOT IMPLEMENTED)

        # SUBMIT alltext to COMPONENT ANALYSIS
        # if conf.getb( "postprocessor", "ocr") and conf.getb( "postprocessor", "ocr_analysis"):
            # ocrdata = jkm.ocr_analysis.ocr_analysis_Luomus(alltext)
            # log.debug(f"{sample.name}: OCR data parsing output: {ocrdata}")
        # else: log.debug(f"{sample.name}: No OCR data parsing attempted.")           
        # SIMPLE IMPLEMENTATION FOR TESTING
        cleantext = jkm.ocr_analysis.cleanup(alltext)
        ocrdata = jkm.ocr_analysis.OCRAnalysisResult()
        ocrdata.append("ocr",cleantext)

         # FOR FURTHER PROCESSING, CHECK IF IDENTIFIER LIST CONTAINS A SINGLE VALID IDENTIFIER
        # In case sample does already have a known identifier, append to to the list
        if sample.identifier: allbkdata.append(sample.identifier)
        sampleids = _UNIQUE(allbkdata)
        if len(sampleids) == 0:
            log.warning("No usable identifiers found")
        elif len(sampleids) > 1:
            log.warning("Several  different identifiers for the sample in barcodes/OCR/sample metadata")
        else: sample.identifier =  sampleids[0] # Sets also sample.shortidentifier
        
       # Store interpreted data in a table file IF data and identifier are available
        if sample.identifier and data_out_table:
            ocrdata.prepend("identifier", sample.identifier) 
            log.debug(f"{sample.name}: Calling OutputCSV.addline with data: {ocrdata}")
            log.debug(f"{sample.name}: data_out_table.fp = {data_out_table.fp}")
            data_out_table.add_line(ocrdata)
            log.debug(f"{sample.name}: ...done")
            
        # RENAME DIRECTORIES (this may need to stay above file renaming)
        if conf.getb( "basic", "directories_rename_by_barcode_id") and sample.identifier:
            prefix = sample.datapath.name # last element of directory path
            log.debug("Renaming directory based on barcode content")
            try:            
                sample.rename_directories(conf,prefix)
            except (jkm.errors.JKError, FileNotFoundError) as msg: 
                log.warning(f"Renaming directory failed: {msg}. Maybe it has already been renamed.")                

        # RENAME FILES
        # Current implementation renames only the original image files as per the configuration file
        if conf.getb( "basic", "files_rename_by_barcode_id") and sample.shortidentifier:
            try:
                sample.rename_all_files(sample.shortidentifier)
            except (jkm.errors.JKError, FileNotFoundError) as msg:
                log.warning(f"Renaming files failed: {msg}.")                

        # Write records to JSON Metadata file (should this be before renaming?)
        if conf.getb( "basic", "save_JSON"): sample.writeMetaJSON()

        # FOR MZH IMAGING LINE SAMPLES
        if conf.get("sampleformat", "datatype_to_load").lower()  in ["mzh_insectline", "mzh_plantline"]:
            # Write postprocessor.properties file 
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
            sample.digipropfile.save( sample.datapath /  Path(r"postprocessor.properties") )
        #DONE
        log.info(f"Sample events in process queue: {q.qsize()}\n\n") # Queue still contains this item, thus -1 in the number reported
           

if __name__ == '__main__':
    threads = []
    excel = None
    q = queue.Queue() # a FIFO queue of metafile names
    log = jkm.tools.setup_logging(_program_name, debug = _debug)
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
        filetype = conf.get("sampleformat", "recognize_by_filename_pattern")
        datafile_patterns = [filetype]
        if conf.getb("postprocessor", "process_existing"):
            existingevents = find_samples( conf.basepath,datafile_patterns )
            for fn in existingevents: q.put(fn)
            log.info(f"Approximate number of sample events to process at launch is {q.qsize()}")
        
        if conf.getb("postprocessor", "ocr_analysis_to_Excel"):
            ocr_outfile = conf.get("ocr","ocr_analysis_Excel_file")
            data_out_table = jkm.ocr_analysis.OutputCSV( ocr_outfile )
            data_out_table.open()
        else: data_out_table = None
        log.debug(f'Using QR code decoder {conf.get( "barcodes", "barcodepackage")}')
         #Start loops looking for data to process and processing it
        for i in range(_num_worker_threads):
            t = threading.Thread(target=processSampleEvents,  args=(conf, sleep_s_before_reading_file, data_out_table))
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
        if data_out_table: data_out_table.save()
    except jkm.errors.JKError as msg:
        log.critical(f'Execution failed with error message "{msg}"')
        raise Exception(msg)
    logging.shutdown()         
