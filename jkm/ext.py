from abc import ABC, abstractmethod
class ExtBase(ABC):
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    @abstractmethod
    def event_exit(self, msg): pass

class DefaultExt(ExtBase):
    def __init__(self): pass
    # stubs for event calls for passing data to a GUI. For now, one direction only!
    def event_exit(self, msg): pass

class PrinterExt(ExtBase):
    def __init__(self): pass
    def event_exit(self, msg): print(msg)


