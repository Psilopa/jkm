# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import logging
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSlot

class Worker(QRunnable):
    @pyqtSlot()
    def set_func(self,target, args):
        self.target = target
        self.args = args
    def run(self):
        """Your long-running job goes in this method."""
        print("Thread start")
        self.target(*self.args)
        print("Thread complete")

class myQThreadPool():
    def __init__(self):
        self.pool = QThreadPool()
    def newthread(self, target=None, args= ()):
        if target:
            worker = Worker()
            worker.set_func(target, args)
            self.pool.start(worker )
    def join(self):
        self.pool.waitForDone()

logging_level_file = logging.DEBUG
logging_level_stream = logging.DEBUG
jkm = jkm_post()
jkm.main(logging_level_file, logging_level_stream, threadpool=myQThreadPool() )
