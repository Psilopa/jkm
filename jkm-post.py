# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import logging

logging_level_file = logging.DEBUG
logging_level_stream = logging.DEBUG
jkm = jkm_post()
jkm.main(logging_level_file, logging_level_stream)
