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
from jkm.digitisation_properties import DigipropFile

_debug = True
_num_worker_threads = 4
_program_name = "jkm-post"
_program_ver = "1.01" 
_program = f"{_program_name} ({_program_ver})"

allowed_URI_domains = ["http://tun.fi/", "http://id.luomus.fi/",""]

# Move to Luomus-specific Sample type
def grab_identifier_prefix(ident): # everything up to the last /
    if not "/" in ident:
        return None
    else:
        parts = ident.split("/")
        noend = "/".join(parts[:-1]) + "/"
        return noend        

# Move to Luomus-specific Sample type
def verify_URI(uri):
    # SIMPLISTIC IMPLEMENTATION
    pref = grab_identifier_prefix(uri)
    if pref is None: return True  # No URI to test
    for uriok in allowed_URI_domains:
        if uriok in uri: return True
    return False # No matching URI pattern found

# Move to Luomus-specific Sample type
def file_add_prefix(sid,old_filename,ignore_domain=True, domain_separator = '/', prefix_separator= "_"):
    """Rename files/dirs if sample ID data is available (from QR code parsing or other source)
##
##    sids = a single identified
##    ignore_domain = if True, only the namespace.number part is used 
##    Renaming details are provided in the config class instance passed as an argument
##
##    """
    try: 
        log.debug(f"Renaming files based on barcode content: SID {sid}, oldname {old_filename}")
        new_pathname = old_filename # Default new name = old name
        if ignore_domain: # Remove http//domains/ from ID
            sid = sid.split(domain_separator)[-1]
        newprefix = sid + prefix_separator
        new_filename = sid + prefix_separator + Path(old_filename).name
        new_pathname = old_filename.parent / Path(new_filename)
        log.debug(f"New name for {old_filename} is {new_pathname}")
        old_filename.rename(new_pathname) 
    except PermissionError as msg:
        log.warning("Renaming file failed with error message: %s" % msg)
    except FileExistsError as msg:
        log.warning("Target file name already exists, skipping: %s" % msg)
    finally: 
        return new_pathname    

# Move to Luomus-specific Sample type
def rename_directories(sids,config,datapath,prefix,ignore_domain=True, separator = '\\'):
    """Rename files/dirs if sample ID data is available (from QR code parsing or other source)

    sids = iterable (list, tuple or similar) with identifiers
    ignore_domain = if True, only the namespace.number part is used 
    Renaming details are provided in the config class instance passed as an argument

    """
    log.debug("Renaming files based on barcode content")
    sids = tuple(dict.fromkeys(sids)) # Remove duplicates
    if len(sids) == 0:
        log.warning("File renaming requested but no usable identifiers found")
        return datapath, prefix # Silently fail if no usable identifier (not the best)        
    if len(sids) > 1:
        log.warning("File renaming requested but several different identifiers found")
        return datapath, prefix # Silently fail if no usable identifier (not the best)        
    sid = sids[0]
    if ignore_domain: # Remove http//domains/ from ID
        sid = sid.split(separator)[-1]

    try: # TODO: EXTEND TO POSSIBLE SUBDIRECTORIES?
        basepath = Path(config.get("basic","main_data_directory"))
        newprefix = sid + "_" + prefix
        if config.getb("basic","create_directories"): # if a subdirectory was created for data
            newbase = basepath / sid # example [basebath]/GX.38276
            newpath = newbase / newprefix # example [basebath]/GX.38276/GX.38276_timestamp
            if not newbase.exists(): newbase.mkdir() 
        else:
            newpath = basepath / newprefix 
        log.debug(f"Renaming {datapath} to {newpath}")        
        datapath.rename(newpath) 
    except PermissionError as msg:
        log.warning("Renaming directory failed with error message: %s" % msg)
    except FileExistsError as msg:
        log.warning("Target directory name already exists, skipping: %s" % msg)
    finally: 
        return newpath

# Move to Luomus-specific Sample type
def find_meta_files(dirname,datafile_patterns):
    log.debug(f"Finding files to process" )
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

# Move to Luomus-specific Sample type
def grab_timestamp_from_dirname(dirname): #helper function for insect line processing
    marker = "dc1."
    x = str(dirname.name).split(marker) # Look for marker in last element of directory name
    if len(x) != 2: return ""
    else: return x[-1] # Last element

class myFileEventHandler(watchdog.events.PatternMatchingEventHandler):
    def __init__(self,  *args,  **kwargs): super().__init__(**kwargs)
    def on_created(self, event): q.put(event.src_path)        

def path_in_list(p,pathlist):
    for p2 in pathlist: 
        if p.samefile(p2): return True
    return False		
    
# ----------------- main worker function ------------------------
def processSampleEvents(conf, sleep_s, data_out_table):
    while True:
#        print("processSampleEvents called")		
        input = q.get()
        if input is None: break
        filename = Path(input)
#        print("STARTING TO SLEEP")
        time.sleep(sleep_s) # Wait for all data to arrive
#        print("END OF SLEEP")
        if not filename.exists():  #" File may aleady have been deleted, renamed etc.
            log.warning(f"Could not find file {filename}, skipping")
            q.task_done(); continue
        log.debug(f"Processing data file {filename}" )
        # Create SampleEvent instances based on (meta)data file(s)
        filesuff = filename.suffix
        try:
            if filesuff.lower() == ".json":
                sample = jkm.sample.SampleEvent.fromJSONfile(filename)
            elif filesuff.lower() in [".jpg",".jpeg"]:             
                sample = jkm.sample.SampleEvent.fromJPGfile(filename, conf, "generic_camera")
#            if filesuff.lower() == ".json":
#                sample = jkm.sample.SampleEvent.fromLinjastoMetadatafile(filename)
            else:
                raise jkm.errors.FileLoadingError("Unknown metadata format")
                q.task_done(); continue
        except jkm.errors.FileLoadingError:
                q.task_done(); continue
        # MAIN POSTPROCESSOR IN HERE
        log.info(f"Postprocessing sample {sample.name}")
        # ROTATE
        rot = conf.geti( "postprocessor", "rotate_before_processing")
        if rot: # non-zero value
            for i in range(len(sample.imagelist)):
                log.debug(f"Rotating image {sample.imagelist[i].name}")
                sample.imagelist[i].rotate(rot)
        # SAVE ROTATED
        
        # FIND BARCODES
        bkdata = []
        if conf.getb( "postprocessor", "read_barcodes"):
            
            log.debug(sample.imagelist)
            for image in sample.imagelist:
                try:
                    bkdata = image.readbarcodes()
                    image.meta.addlog("Barcode contents",bkdata)
                except jkm.errors.FileLoadingError as msg:
                    log.warning("Barcode detection attempt failed: %s" % msg)
                    continue
        # FIND TEXT ARES
        if conf.getb( "postprocessor", "find_text_areas"):
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                log.debug(f"Searching for text areas in {image.camname} of sample {sample.name}")
                neuralnet = conf.get( "ocr", "EASTfile")
                textareas = image.findtextareas(neuralnet)
                image.meta.addlog("Text areas found", str(textareas))
                if conf.getb( "postprocessor", "save_text_area_images"): 
                    image.savetextareas("_textarea_")
        # PERFORM OCR
        if conf.getb( "postprocessor", "ocr"):
            alltext = ""
            for image in sample.imagelist:
                if not image.has_labels : continue # Skip pure specimen images
                labeltxt = image.ocr() # Default ocr uses fragments created above
                alltext  += " " + labeltxt
#                image.meta.addlog("OCR result for image", labeltxt,lvl=logging.DEBUG)
            sample.meta.addlog("Combined OCR result for all images",alltext)

        # SUBMIT alltext to component analysis
        ocrdata = None
        if conf.getb( "postprocessor", "ocr") and conf.getb( "postprocessor", "ocr_analysis"):
            ocrdata = jkm.ocr_analysis.ocr_analysis_Luomus(alltext)
            log.debug(f"OCR data parsing output: {ocrdata}")
        else: log.debug("No OCR data parsing attempted.")      
        
        sids = bkdata
        datapath = sample.datapath
        sids = [x.split('/')[-1] for x in sids] # List of sample identifiers (short form)
        # Store interpreted data in a table file IF data and identifier are available
        if ocrdata and len(sids) == 1:
            fullbarcode = bkdata[0]
            ocrdata.prepend("identifier", fullbarcode)
            log.debug(f"Calling OutputCSV.addline with data: {ocrdata}")
            log.debug(f"data_out_table.fp = {data_out_table.fp}")
            data_out_table.add_line(ocrdata)
            log.debug("...done")
            
        # RENAME DIRECTORIES (this should be before file renaming
        if conf.getb( "basic", "directories_rename_by_barcode_id") and bkdata:
            prefix = sample.datapath.name # last element of directory path
            datapath = rename_directories(sids,conf,datapath,prefix)
            sample.datapath = datapath
        # RENAME FILES
        if conf.getb( "basic", "files_rename_by_barcode_id") and bkdata and len(sids) == 1:
            # TODO: THIS DOES NOT UPDATE DATA IN SAMPLE CLASSES
            for filepath in sample.filelist:
                file_add_prefix(sids[0], filepath)

        # Write records to Metadata file
        if conf.getb( "basic", "save_JSON"): sample.writeMetaJSON()
        # Insect line-specific stuff, should be moved into a subclass
        # Grab timestamp from dirname
        timestamp = grab_timestamp_from_dirname(sample.datapath)
        # Write sampleID to Linjasto metadata file (if any)
        # TODO: move this to a function in DigiLineSample (or any other relevant sample type)         
        if conf.get("postprocessor", "datatype_to_load") == "Preview002.jpg":
            if len(sids) == 1:
                outsid = sids[0]
                fullbarcode = bkdata[0]
                url_OK = verify_URI(fullbarcode)
                log.debug(f"URI prefix {grab_identifier_prefix(fullbarcode)}")
                if not url_OK: log.critical(f"*******\n\n\n\nMALFORMED IDENTIFIER {fullbarcode}*******\n\n\n\n")
            else:
                log.warning("No readable QR code, or several QR codes")
                outsid = ""
                fullbarcode = ""
                url_OK = False
            fn = Path(r"postprocessor.properties")
            log.info(f"Updating file {fn} with identifier {outsid}\n")
            fullpath = sample.datapath / fn
            #make backup copy
            #backuppath = sample.datapath / Path("~" + str(fn))
            #shutil.copy(fullpath, backuppath) # make a copt of the old .properties file before updating
            # Read, update and write
            log.debug(f"identifier: {outsid}, datapath = {sample.datapath}")
            dpr = DigipropFile()    
#            with open(fullpath,"r") as f: dpr.read(f)
            dpr.setheader( f"# {datetime.now()}" )
            dpr.update("full_barcode_data",fullbarcode)
            dpr.update("identifier",outsid)
            dpr.update("timestamp",timestamp)
            dpr.update("URI_format_OK", str(url_OK) )
            dpr.update("Q-sharp", "" )
            dpr.update("Q-color", "" )
            if conf.getb( "postprocessor", "ocr"): dpr.update("OCR_result", alltext.replace("\n"," "))
            with open(fullpath,"w") as f: dpr.write(f)
        log.info(f"Sample events in process queue: {q.qsize()-1}\n\n") # Queue still contains this item, thus -1 in the number reported
           

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
    conf = jkm.configfile.load_configuration(_program_name) 
	# Wait period from file detection to file processing
	# Allows for enough time for transfer of a file(s)  to be completed
    sleep_s_before_reading_file = conf.getf("postprocessor", "sleep_after_new_sample_detected")
    # TODO: get data types to process from config file: event packages (identified by metadata files) or simple image files
    filetype = conf.get("postprocessor", "datatype_to_load")
    if filetype.lower() == 'jpg': datafile_patterns = ['*.jpg']
    #elif filetype.lower() == 'json': datafile_patterns = ['*.json']
    #elif filetype.lower() == 'linjasto_metadata': datafile_patterns = ['metadata'] # TODO: Load directory as sample
    else: datafile_patterns = [filetype]
        
    if conf.getb("postprocessor", "process_existing"):
        existingevents = find_meta_files(conf.basepath,datafile_patterns)    
        for fn in existingevents: q.put(fn)
        log.info(f"Approximate number of sample events to process at launch is {q.qsize()}")
    
    if conf.getb("postprocessor", "ocr_analysis_to_Excel"):
        data_out_table = jkm.ocr_analysis.OutputCSV("test.csv")
        data_out_table.open()
     
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
    logging.shutdown()         
