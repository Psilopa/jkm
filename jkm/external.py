# For typing
from jkm.typing import *
import logging

class ExtBase():
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    def event_exit(self, msg:str): pass
    def event_log(self, logrecord:logging.LogRecord): pass
    def event_ai_labeltext(self, sample:type_sample): pass
    def event_textareas(self, sample:type_sample): pass
    def event_OCRtext(self, sample:type_sample): pass
    def event_barcode_detection(self, sample:type_sample): pass
    def event_new_sample(self, sample:type_sample): pass
    def event_single_sample_id(self, sample:type_sample): pass
    def event_renamed_directories(self, sample:type_sample): pass
    def event_renamed_image_files(self, sample:type_sample): pass
    def event_sample_done(self, sample:type_sample, successQ:bool): pass

class PrinterExt(ExtBase):
    def __init__(self): pass
    def event_exit(self, msg:str)-> None: print(msg)
    def event_log(self, logrecord: logging.LogRecord)-> None: print(logrecord.message)


