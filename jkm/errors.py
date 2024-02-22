import logging

log = logging.getLogger() # Overwrite if needed

class LoggingError(Exception):
    def __init__(self, msg,  level = logging.ERROR):
        log.log(level,  msg)
        Exception.__init__(self,msg)

class CameraError(LoggingError):
    def __init__(self, msg): LoggingError.__init__(self,msg)

class OCRError(LoggingError):
    def __init__(self, msg): LoggingError.__init__(self,msg)

class BarcodeError(LoggingError):
    def __init__(self, msg): LoggingError.__init__(self,msg)

class FileLoadingError(LoggingError):
    def __init__(self, msg): LoggingError.__init__(self,msg)
