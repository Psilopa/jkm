# -*- coding: utf-8 -*-
import logging

log = logging.getLogger() # Overwrite if needed

class JKError(Exception): 
    def __init__(self, msg): Exception.__init__(self,msg)

class LoggingError(JKError):
    def __init__(self, msg,  level = logging.ERROR):
        log.log(level,  msg)
        super().__init__(msg)

class ConfigError(LoggingError):
    def __init__(self, msg): super().__init__(msg)

class ConfigWarning(LoggingError):
    def __init__(self, msg): super().__init__(msglevel = logging.WARNING)

class OCRError(LoggingError):
    def __init__(self, msg): super().__init__(msg)

class BarcodeError(LoggingError):
    def __init__(self, msg): super().__init__(msg)

class FileLoadingError(LoggingError):
    def __init__(self, msg): super().__init__(msg)

class AIError(LoggingError):
    def __init__(self, msg): super().__init__(msg)
