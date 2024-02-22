# import atexit
import logging,  subprocess
from pathlib import Path
import jkm.configfile,  jkm.camera,  jkm.tools,  jkm.sample
from jkm.errors import *
from pynput import keyboard
from shutil import disk_usage


_help = """
%s = take image and postprocess it HOTKEY (works even if the program window is not in focus)
i = take image and postprocess it
f = display free space remaining on disk
r = reload settings data
h/? = display help
e/q = exit program
"""

formatext = ".jpg"
_spacewarn = 300*(1024)**2 # 300 MB
_program_name = "jkm"
_program_ver = "0.2"
_program = f"{_program_name} ({_program_ver})"

# keyboard import processing helpers
_imagingkeycode = '<cmd>+i' # Windows-i for imaging

# --- datafile load helper ----                
def load_datafile(fn,load_func,msg=""):
    if fn:
        fnp = Path(fn)
        if not fnp.exists(): raise FileLoadingError("File %s does not exist" % fnp)
        if not fnp.is_file(): raise FileLoadingError("%s is not a file" % fnp)
        if not fnp.is_reserved(): raise FileLoadingError("File %s is reserved" % fnp)
        if msg: log.info(msg % fn)
        return load_func(Path(fnp))
    else: return ()

class MainImagingProgram():
    # TODO: add basic data quality checks 
    def __init___(self):
#        self.datapath = None
        self.cameras = []
        self.known = {}
        self.skip = []
        self.event = None
        self.imagingkeycode = _imagingkeycode # set default value
    def exit(self):
        log.debug("Ending session, closing connections to all cameras")
        for cam in self.cameras: cam.stop() 
        log.info("Ending session, closing log files")
        logging.shutdown()        
    def load_config(self):
        log.info("Reloading configuration data")
        self.conf = jkm.configfile.load_configuration(_program_name) # configuration class instance
        log.info(f"Output path base is {self.conf.basepath}" )
        if not self.conf.basepath.exists():
            log.warning("Output base bath does not exist, creating it.")
            self.conf.basepath.mkdir()
        self.imagingkeycode = self.conf.get('basic','imaging_hotkey')
    def find_cameras(self):
        "Load camera data based on config file data"
        self.cameras = jkm.camera.FindCameras(self.conf) 
        for cam in self.cameras:
            try:
                cam.start()
                if not cam.is_usable: log.warning(f"Camera {cam.name} is not available " )
                else: log.debug( f"Camera {cam.name} is started" )
            except CameraError: pass # Automatically logs error, camera remains in is_usabe = False
#    def load_known_data(self):
#        "Load data files related to OCR (if available)"
#       self.known = {}
#        for knfn in self.conf .getlist("ocr","known_data_items_files",fallback=[]):
#            known.update(load_datafile(knfn,jkocr.load_known_data,"Loading known data items from file %s" ))
#        excluded_strings_file = self.conf.get("ocr","excluded_strings_file",fallback=None)
#        self.skip = load_datafile(excluded_strings_file,jkocr.load_skip_data,"Loading excluded strings from file %s")
    def take_images(self):
            log.info("Received Imaging trigger")
            jkm.tools.monitor_disk_space( self.conf.basepath, _spacewarn )
            # Create Sample Imaging Event instance
            self.event = jkm.sample.SampleEvent()
            self.event.copyMetadatafFomConf(self.conf)
            for camera in self.cameras: # TODO: TURN THIS INTO A MULTITHREAD OPERATION, ALLOWING FOR SIMUL DOWNLOADS ETC?               
                if not camera.is_usable:
                    self.event.meta.addlog(f"{camera.name} - ERROR" , "camera not in an usable state",logging.WARNING)
                    continue
                log.info(f"{camera.name} - capturing data")
                imagetype = camera.objecttype
                sampleimg = jkm.sample.create_new_image(imagetype)
                sampleimg.cameraname = camera.name
                sampleimg.confsection = camera.section
                barefilename = "_".join([self.event.prefix, camera.name + formatext])
                sampleimg.filename = self.event.datapath / barefilename                
                try:
                    camera.capture_and_store_jpg(sampleimg.filename)
                    sampleimg.copyMetadatafFomConf(self.conf)
                    sampleimg.addlogMeta("original file name", barefilename)
                    sampleimg.addlogMeta("keywords", camera.keywords)
                    self.event.addImage(sampleimg)
                except CameraError as err: 
                    self.event.meta.addlog(f"{camera.name} - ERROR: Capturing image from camera failed", err, logging.ERROR)
#                except BarcodeError as err: 
#                    self.event.meta.addlog("%s - WARNING: Barcode reading failed" % camera.name, err, logging.WARNING)
                except subprocess.TimeoutExpired as err: 
                    self.event.meta.addlog(f"{camera.name}- WARNING: Timeout on image capture", err, logging.WARNING)
            # Postprocess, if requested
            # Basic data quality checks
            #Save metadata
            self.event.writeMetaJSON()
            
    def _setup_hotkeys(self):
        def for_canonical(f): return lambda k: f(self.hotkeylistener.canonical(k))
        hotkey = keyboard.HotKey( keyboard.HotKey.parse( self.imagingkeycode ), self.take_images )
        self.hotkeylistener = keyboard.Listener( on_press=for_canonical(hotkey.press), on_release=for_canonical(hotkey.release)) 
        self.hotkeylistener.start()
        
    def main_loop(self):
        # Listen to keyboard event, launch
        self._setup_hotkeys()
        while True: 
                command = input('Command: ').strip()
                if command in ("I","i"): # Take and store images + basic metadata
                    self.take_images()                                               
                elif command in ("F","f"): # Disk space check
                    freeb = disk_usage(self.conf.basepath).free
                    print("Free disk %.0f MB (%.1f GB)" % (freeb/(1024**2),(freeb/(1024**3))))
    #                if self.datapath:
    #                    lastdirused = sum(file.stat().st_size for file in Path(datapath).rglob('*'))
    #                    if lastdirused > 0: # TODO: keep size of last run in config??
    #                        print("there is still space for about %.0f samples on this disk" % (freeb/lastdirused))
    #                        print("last sample used %.2f MB " % (lastdirused/(1024**2)))
                elif command in ("E","e","Q","q"): break # QUIT
                elif command in ("h","H","?"): print(_help % self.imagingkeycode)
                elif command in ("R","r"): # Reload configuration TODO: force reloading or neural net
                    self.load_config()
                    self.find_cameras()
                    self.hotkeylistener.stop() 
                    self._setup_hotkeys() 

if __name__ == '__main__':
    log = jkm.tools.setup_logging(_program_name)
    log.info(f"STARTING NEW SESSION of {_program}")
    # Set loggers in other modules
    jkm.configfile.log = log    
    jkm.camera.log = log
    jkm.tools.log = log
    jkm.sample.log = log

    m = MainImagingProgram()
    m.load_config()
    m.find_cameras()
    m.main_loop()
    m.exit()

## At exit functions (these do not work in the IDLE environments
#def closecams(cameras):
#    log.debug("Exiting, closing connections to all cameras")
#    for cam in cameras: cam.stop() 
#def closeloggers():
#    log.info("Ending session, closing log files")
#    logging.shutdown()    
## last registered, first called!
#atexit.register(closeloggers)
#atexit.register(closecams,cameras)
