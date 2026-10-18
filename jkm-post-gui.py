# -*- coding: utf-8 -*-
import atexit, re, logging
# Local
from jkm.jkm_postprocessing_main import jkm_post
import jkm.meta, jkm.external, jkm.ai
# QT
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSlot, pyqtSignal, QObject
import PyQt6.QtWidgets as QtWidgets
from PyQt6 import uic # for uic, install package pyqt6-dev-tools 

# Translates jkm output to QT Signals
class QExt(jkm.external.ExtBase, QObject):
    newLogEvent = pyqtSignal(logging.LogRecord)
    newAILabelText = pyqtSignal(jkm.ai.AI_output)
    def event_exit(self, msg): pass
    def __init__(self):
        QObject.__init__(self)
        jkm.external.ExtBase.__init__(self)

    def event_log(self, logrecord): self.newLogEvent.emit( logrecord )
    #Sample-specific messages
    def event_ai_labeltext(self, sample):
        self.newAILabelText.emit( sample.results.labeltext_ai1 )
    def event_textareas(self, sample): pass
    def event_OCRtext(self, sample): 
        ocrtext = sample.results.ocrtext
    def event_barcode_detection(self, sample): 
        barcodes = sample.results.barcodes
    def event_new_sample(self, sample): pass
    def event_single_sample_id(self, sample): 
        sid = sample.identifier
    def event_renamed_directories(self, sample): pass
    def event_renamed_image_files(self, sample): pass
    def event_sample_done(self, sample, successQ): pass

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

def _str(x): return x if isinstance(x, str) else x.group(0)
def color(x, color): return rf"<font color={color}>{_str(x)}</font>" 
def bold(x): return rf"<b>{_str(x)}</b>" 
def grey(x): return color(x,"gray") 
def red(x): return color(x,"red") 
def red_bold(x): return red(bold(x))
def nothing(x): return _str(x)
def empty(x): return ""
formattingrules = [
    (re.compile(r"({.*?})"), bold ), # AI JSON output string embadded in log
    (re.compile(r"DEBUG:*"), grey),
    (re.compile(r"INFO:\s"), empty),
    (re.compile(r"WARNING:*"), red),
    (re.compile(r"ERROR:*"), red_bold),
    (re.compile(r"CRITICAL:*"), red_bold),
    ]

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
    def activethreadcount(self): return self.activeThreadCount() 
    def join(self):
        self.waitForDone()

class MainWindow(QtWidgets.QMainWindow):
    rules = formattingrules
    def __init__(self, *args, **kwargs):
        if "ext" in kwargs:
            self.ext = kwargs["ext"]
            del kwargs["ext"]
        super().__init__(*args, **kwargs)
        self.logging_level_file = logging.DEBUG
        self.logging_level_stream = logging.INFO
        self.threadpool = None
        self.jkm = None
        self._load_UI()
        self._connectSignalsSlots() # Do this only after jkm is created
        self.show()
        self.launch_jkm()
    def _load_UI(self):
        """Read an GUI definition file and connect it to data models"""
        uic.loadUi("gui/mainwindow.ui", self)
        self.setWindowTitle(jkm.meta.nameversion)

    def _connectSignalsSlots(self):
        self.actionExit.triggered.connect(self.on_exit)
        self.actionExit.triggered.connect(self.on_exit)
        # self.ext *should* be in place by now
        if self.ext:
            self.ext.newLogEvent.connect(self.on_logevent)
            self.ext.newAILabelText.connect(self.on_ailabel)
    
    def launch_jkm(self):
        self.threadpool = myQThreadPool() 
        self.jkm = jkm_post()
        self.jkm.main(self.logging_level_file,
                      self.logging_level_stream,
                      threadpool=self.threadpool,
                      ext = self.ext 
                      )

    def on_ailabel(self, ai_data):
        endline = "<br/>"
        suppress_raw = True
        text = ai_data.to_prettyprint(endline)
        if text: 
            self.aiviewer.insertHtml(text + endline)

    def on_logevent(self, logrecord):
        levelname = logrecord.levelname
        text = logrecord.message
        text = f"{levelname}: {text}"
        self.add_logmsg(text)

    def add_logmsg(self,htmltext, endline = "<br/>"): # Reused from LabelImaging
        if not endline: endline = ""
        for re_object, processor in self.rules:
            htmltext = re_object.sub(processor, htmltext)
        self.logviewer.insertHtml(htmltext + endline)
        self.logviewer.ensureCursorVisible() # Force scroll to bottow

    def on_exit(self):        
        if self.jkm: self.jkm = None
        self.close()

ext = QExt() # Create jkm-QT communication facilitator first
app = QtWidgets.QApplication([])
window = MainWindow(ext = ext)
app.exec()


