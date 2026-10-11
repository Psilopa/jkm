# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import atexit
import jkm.ext
import logging
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSlot
import PyQt6.QtWidgets as QtWidgets

# Hook to jkm output
class QExt(jkm.ext.ExtBase):
    def __init__(self,parent):
        self.parent = parent
    def event_exit(self, msg):
        showDialog(self.parent, msg)
    
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

class myQThreadPool():
    def __init__(self):
        self.pool = QThreadPool()
    def newthread(self, target=None, args= ()):
        if target:
            worker = Worker()
            worker.set_func(target, args)
            self.pool.start(worker )
    def join(self):
        log.debug("Watining for threads to close.")
        self.pool.waitForDone()

class MainWindow(QtWidgets.QMainWindow):
    def launch_jkm(self):
        self.threadpool = myQThreadPool() 
        thread_count = self.threadpool.pool.maxThreadCount()
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


        self.show()
        self.launch_jkm()

app = QtWidgets.QApplication([])
window = MainWindow()
app.exec()



