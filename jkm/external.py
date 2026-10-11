class ExtBase():
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    def event_exit(self, msg): pass
    def event_ai_output(self, container): pass
    def event_log(self, logrecord): pass

class DefaultExt(ExtBase):
    def __init__(self): pass
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    def event_exit(self, msg): pass
    def event_log(self, logrecord): pass

class PrinterExt(ExtBase):
    def __init__(self): pass
    def event_exit(self, msg): print(msg)
    def event_ai_output(self, container): print(container)
    def event_log(self, logrecord): print(logrecord.message)


