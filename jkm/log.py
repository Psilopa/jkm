import logging, os

LOG_FILE_ENCODING = "utf8"
       
class ColorFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    white = "\x1b[0m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    def __init__(self, formatstr):
#        formatstr = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)" 
        self.FORMATS = {
            logging.DEBUG: self.grey + formatstr + self.reset,
            logging.INFO: self.white + formatstr + self.reset,
            logging.WARNING: self.yellow + formatstr + self.reset,
            logging.ERROR: self.red + formatstr + self.reset,
            logging.CRITICAL: self.bold_red + formatstr + self.reset,
        }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
            
# Send log data to an external reader via an event
class ExtHandler(logging.Handler):
    def __init__(self, ext):
        super().__init__()
        self.ext = ext
    def emit(self,record): self.ext.event_log(record)

def setup_logging(name,
                  logging_level_file = logging.INFO,
                  logging_level_stream = logging.INFO,
                  ext = None):
    """Set up logging services"""
    STREAMLOGFORMAT = '[%(asctime)s] %(message)s'
#    STREAMLOGFORMAT = '%(message)s'
    FILELOGFORMAT = '%(levelname)s: %(message)s [%(asctime)s]'
    #TODO: Call needed on windows only!
    os.system('color')  # Ask system console to display color if available
    # Default logger: should do nothing as we add our own handlers, but set just in case
    log = logging.getLogger(name)
    log.setLevel(logging_level_file)
    # To console
    consolelog = logging.StreamHandler( )
    consolelog.setFormatter(ColorFormatter(STREAMLOGFORMAT))
    consolelog.setLevel( logging_level_stream )
    log.addHandler(consolelog)
    # To log file
    filelog = logging.FileHandler(f"{name}.log",  encoding=LOG_FILE_ENCODING)
    filelog.setFormatter(ColorFormatter(FILELOGFORMAT))
    filelog.setLevel( logging_level_file )
    log.addHandler(filelog)
    # To ext
    if ext:
        extlog = ExtHandler(ext)
        # At least for now, default external logging to use the same settings as stream
        extlog.setLevel( logging_level_stream ) 
        extlog.setFormatter( logging.Formatter(fmt=FILELOGFORMAT) ) 
        log.addHandler(extlog)
    log.info(f"Console logging set to level { logging.getLevelName(logging_level_stream) }.")
    return log
