import shutil, subprocess, logging, abc
from pathlib import Path
import cv2
from jkm.errors import *

log = logging.getLogger() # Overwrite if needed

camera_subprocess_timeout = 15
# Flag to suppressshell window display for subprocesses on Windows
CREATE_NO_WINDOW = 0x08000000 

# TODO: ERRORS TO METADATA FILE
# TODO: WRITE CAMERA METADATA into file

# ------ Camera (abstract) base class  -------------
class Camera(abc.ABC):
    has_still_capture = False
#    has_video_capture = False
    def __init__(self,name):
        self.name = name
        self.is_usable = False        
        self.section  = None
        self.objecttype  = None
    def start(self): log.debug(f"Starting camera {self.name}" ) # Default, only logging
    def stop(self): log.debug(f"Stopping camera {self.name}") # Default, only logging
    @abc.abstractmethod
    def capture_and_store_jpg(self,fn): pass

# ------ Camera classes for various interaction methods-------

class TestCamera(Camera): # For testing
    def __init__(self,name,fn):
        Camera.__init__(self,name)
        self.has_still_capture=True
        self.fn = Path(fn)
        self.is_usable = False
    def capture_and_store_jpg(self,fn):
        self._capture_jpg()
        self._store_jpg(fn)
    def start(self):
        Camera.start(self)
        if not self.fn.exists(): raise CameraError(f"Test file not found: {self.name}")
        self.is_usable = True
    def _capture_jpg(self): pass
    def _store_jpg(self,fn):
        if not self.fn.exists(): raise CameraError(f"Test file not found: {self.name}")
        if fn.exists(): raise CameraError(f"Target file already exists: {fn}")
        shutil.copy2(self.fn,fn)

class opencvCamera(Camera):
    def __init__(self,name):
        Camera.__init__(self,name)
        self.has_still_capture = True
        self.frame = None
        self.is_usable = False
        self.vidcap = None
        self.number = None
    def start(self):
        Camera.start(self)
        self.is_usable = True        
        self.vidcap = cv2.VideoCapture(1)
    def  _capture_jpg(self):
        ret,frame = self.vidcap.read()
        if ret is False: raise CameraError(f"Video frame capture failed for camera {self.name}")
        self.frame = frame
        # Test result here
    def _store_jpg(self,fn):
        if type(self.frame) is not type(None):
            log.debug(f"Writing file {fn}" )
            cv2.imwrite(str(fn), self.frame)
    def capture_and_store_jpg(self,fn):
        self._capture_jpg()
        self._store_jpg(fn)
    def stop(self):
        Camera.stop(self)
        self.vidcap.release()
        self.vidcap = None
        self.frame = None
        self.is_usable = False

class osCommandCamera(Camera):
    "os.system call-based"
    cmd_capture_base = None
    has_still_capture = True
    def __init__(self,name):
        Camera.__init__(self,name)
    def setCommandBase(self,cmd):
        self.cmd_capture_base = cmd
    def start(self):
        Camera.start(self)
        self.is_usable = True
    def capture_and_store_jpg(self,fn):
        cmd = r'%s "%s"' % (self.cmd_capture_base, fn)
        log.debug(f"Running command {cmd}")
        res = subprocess.run(cmd,capture_output=True, timeout=camera_subprocess_timeout, creationflags=CREATE_NO_WINDOW)
        # TODO: Error processing
        i = res.returncode
        log.debug(f"Camera command return stderr {res.stderr}")
        log.debug(f"Camera command return stdout {res.stdout}")
        log.debug(f"Camera command return value {i}")
        if i != 0:
            raise CameraError(f"Camera {self.name}: imaging failed with error code {i}")
            
class dccCamera(Camera):
    "DigiCamControl-based camera"
    cmd_capture_base = None
    has_still_capture = True
    def __init__(self,name,identifier):
        Camera.__init__(self,name)
        self.identifier = identifier
    def setCommandBase(self,cmd):
        self.cmd_capture_base = cmd
    def start(self):
        # TODO
        Camera.start(self)
        # test access        
#        cmd1 = r'%s /c set camera %s' % (self.cmd_capture_base, self.identifier) # Camera by serial number
#        res = subprocess.run(cmd1,capture_output=True, timeout=camera_subprocess_timeout, creationflags=CREATE_NO_WINDOW)
#        if ":null" in res.stdout.decode("utf8"):
#            log.debug("%s - camera initialisation failed with error %s" % \
#                      (self.name, res.stdout.decode("utf8")))
#            self.is_usable = True # TEST
#        else:
        self.is_usable = True
        return self.is_usable
    def _check(self,res):
        stdo = res.stdout.decode("utf8").strip()
        if ":error;" in stdo:
            log.debug(f"Camera command return stdout {stdo}" )
            raise CameraError(f"Camera {self.name}: imaging failed with error message {stdo}")
#        i = res.returncode
#        if i != 0:
#            log.debug("Camera command return value %s", i)
#            raise CameraError("Camera %s: imaging failed with error code %s" % (self.name,i))        
    def capture_and_store_jpg(self,fn):
        # Select camera in dcc
        cmd1 = r'%s /c set camera %s' % (self.cmd_capture_base, self.identifier) # Camera by serial number
        log.debug(f"Running command '{cmd1}'")
        res = subprocess.run(cmd1,capture_output=True, timeout=camera_subprocess_timeout, creationflags=CREATE_NO_WINDOW)
        self._check(res)
        cmd2 = r'%s /c capture %s' % (self.cmd_capture_base, fn) # Camera by serial number
        log.debug(f"Running command '{cmd2}'")
        res = subprocess.run(cmd2,capture_output=True, timeout=camera_subprocess_timeout, creationflags=CREATE_NO_WINDOW)
        self._check(res)
#        cmd = r'%s "%s"' % (self.cmd_capture_base, fn)
#        log.debug("Running command '%s'" % cmd)
            
##class PTPCamera(Camera):
##    # TODO: CHECK FEATURES ON STARTUP
##    has_still_capture = True
##    def __init__(self,name,description=""):
##        Camera.__init__(self,name,description)
##        self.cam = None
##    def start(self):
##        Camera.start(self)
##        try:
##            self.cam = ptpy.PTPy(raw=True)
##            self.is_usable = True
##            log.debug("Camera report" + self.cam.get_device_info())
##        except:
##            err = sys.exc_info()[1]
##            log.error("Connecting to camera %s failed with message: %s" % (self.name,err))
##            log.error("Camera %s will be ignored!" % self.name.upper())
##    def capture_and_store_jpg(self,fn):
##        with self.cam.session():
##            log.debug("Attempting image capture with camera %s" % self.name)
##            self.cam.initiate_capture()
##            log.info(" ... ok")

##class v4l2Camera(Camera): 
##    has_still_capture = True
##    has_video_capture = False
##    fsize = "800x600"
##    def __init__(self,name,description=""):
##        Camera.__init__(self,name,description)
##    def start(self):        
##        Camera.start(self)
##        self.is_usable = True
##    def capture_and_store_jpg(self,fn):
##        cmd = "ffmpeg -f video4linux2 -i /dev/video0 -s %s -f image2 " % self.fsize
##        cmd += str(fn)
##        i = os.system(cmd)
##        log.debug("Camera command return value %s", i)
##        if i != 0:
##            raise CameraError("Camera %s: imaging failed with error code %s" % (self.name,i))
##        
            
def FindCameras(config):
    """Return list of (usable) cameras based on config file data"""
    c = [] # List of cameras
    cf = config
    for i in range(1, 11): # camera1 ... camera10
        section = "camera%i" % i
        if not cf.has_section(section): continue
        interface = cf.get(section, 'interface')
        cam = None
        name = cf.get(section, 'name')
        if interface.lower() == 'webcam':
            cam = WebCamera(name)            
        elif interface.lower() == 'opencv_webcam':
            cam = opencvCamera(name)
            cam.number = cf.get(section,'camera_number')
        elif interface.lower() == 'opencv_slr':            
            cam = opencvCamera(name)
            cam.number = cf.get(section,'identifier')
        elif interface.lower() == 'digicamcontrol':
            # Try to figure out camera identifier
            if not cf.get(section,'serial_number') and not cf.get(section, 'camera_name'): log.warning(f"No camera identifier given for camera {name}")
            if not cf.get(section,'call'): log.warning(f"No command given for camera {name}")
            cam = dccCamera(name, cf.get(section,'serial_number'))
            cam.setCommandBase(cf.get(section,'call'))
#        elif interface.lower() == 'v4l2':cam = v4l2Camera(name)
  #      elif interface.lower() == 'ptp': cam = PTPCamera(name)
        elif interface.lower() == 'oscall':
            cam = osCommandCamera(name)
            call = cf.get(section,'call')
            if not call: log.warning(f"No command given for camera {name}")
            cam.setCommandBase(call)
        elif interface.lower() == 'test':
            try: fn = cf.get(section,'testimage')
            except KeyError as err:
                log.error(f"No test image gives for TestCamera, exiting ({err})")
                sys.exit()
            cam = TestCamera(name, fn)
        else: log.warning(f"Camera type {repr(interface)} unrecognised" )
        # Set basic properties common for all cameras
        cam.section = section
        cam.objecttype = cf.get(section,'object_type')
        cam.keywords = cf.get(section,'keywords', fallback="")
        # Test Camera
        if cam and cam.has_still_capture:
            c.append(cam)
        else:
            raise CameraError( f"Camera {name} does not support image capture" )
    if len(c) == 0: log.warning( "No cameras registered from setup file." )
    return c    
