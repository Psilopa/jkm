# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import jkm.ext
import logging
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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

class MainWindow(QMainWindow):
    def launch_jkm(self):
        self.threadpool = myQThreadPool() 
        thread_count = self.threadpool.pool.maxThreadCount()
        print(f"Multithreading with maximum {thread_count} threads")
        self.jkm = jkm_post()
        self.jkm.main(self.logging_level_file,
                      self.logging_level_stream,
                      threadpool=self.threadpool,
                      ext = jkm.ext.PrinterExt()
                      )
    def __init__(self, *args, **kwargs):
        self.logging_level_file = logging.DEBUG
        self.logging_level_stream = logging.DEBUG
        self.threadpool = None
        super().__init__(*args, **kwargs)


        self.show()
        self.launch_jkm()

app = QApplication([])
window = MainWindow()
app.exec()
