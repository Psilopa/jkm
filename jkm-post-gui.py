# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import jkm.meta
import atexit
import jkm.external
import logging
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSlot, pyqtSignal
import PyQt6.QtWidgets as QtWidgets
from PyQt6 import uic # for uic, install package pyqt6-dev-tools 

# Hook to jkm output
class QExt(jkm.external.ExtBase):
    def __init__(self,parent):
        self.parent = parent
    def event_exit(self, msg):
        pass
    def event_ai_output(self, container): pass
    def event_log(self, logrecord):
        pass
#        self.newLogEvent.emit( logrecord )
    
@atexit.register
def atExit():
    # Make sure postprocessor shutdown gets called even at unusual program exits
    pass

# QT-based ext message handler

def showDialog(parent, msg, title = "Note"):
   msgBox = QtWidgets.QMessageBox(parent)
   msgBox.setText(msg)
   msgBox.setWindowTitle(title)
   msgBox.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok ) 
   msgBox.setIcon(QtWidgets.QMessageBox.Icon.Question)
   msgBox.exec()


# Use a QThread-based threadpool to avoid UIlockups
class Worker(QRunnable):
    @pyqtSlot()
    def set_func(self,target, args):
        self.target = target
        self.args = args
    def run(self):
        self.target(*self.args)

class myQThreadPool(QThreadPool):
    def __init__(self):
        super().__init__()
    def newthread(self, target=None, args= ()):
        if target:
            worker = Worker()
            worker.set_func(target, args)
            self.start(worker )
    def join(self):
        log.debug("Watining for threads to close.")
        self.waitForDone()

class MainWindow(QtWidgets.QMainWindow):
#    newLogEvent = pyqtSignal(logging.LogRecord)
    def launch_jkm(self):
        self.threadpool = myQThreadPool() 
        thread_count = self.threadpool.maxThreadCount()
        print(f"Multithreading with maximum {thread_count} threads")
        self.jkm = jkm_post()
        self.jkm.main(self.logging_level_file,
                      self.logging_level_stream,
                      threadpool=self.threadpool,
                      ext = QExt(self) # Pass the mainwindow to the event handler
                      )
    def __init__(self, *args, **kwargs):
        self.logging_level_file = logging.DEBUG
        self.logging_level_stream = logging.DEBUG
        self.threadpool = None
        super().__init__(*args, **kwargs)
        self._load_UI()
        self._connectSignalsSlots()

        self.show()
        self.launch_jkm()

    def _load_UI(self):
        """Read an GUI definition file and connect it to data models"""
        uic.loadUi("gui/mainwindow.ui", self)
        self.setWindowTitle(jkm.meta.nameversion)

    def _connectSignalsSlots(self):
        self.actionExit.triggered.connect(self.on_exit)
    
    def on_exit(self):        
        if self.jkm: self.jkm = None
        self.close()

app = QtWidgets.QApplication([])
window = MainWindow()
app.exec()



