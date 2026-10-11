class ExtBase():
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    def event_exit(self, msg): pass
    def event_log(self, logrecord): pass
    def event_ai_labeltext(self, sample): pass
    def event_textareas(self, sample): pass
    def event_OCRtext(self, sample): pass
    def event_barcode_detection(self, sample): pass
    def event_new_sample(self, sample): pass
    def event_single_sample_id(self, sample): pass
    def event_renamed_directories(self, sample): pass
    def event_renamed_image_files(self, sample): pass
    def event_sample_done(self, sample, successQ): pass

class PrinterExt(ExtBase):
    def __init__(self): pass
    def event_exit(self, msg): print(msg)
    def event_log(self, logrecord): print(logrecord.message)


