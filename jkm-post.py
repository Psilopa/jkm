# -*- coding: utf-8 -*-
import jkm.jkm_postprocessing_cli
import logging

logging_level_file = logging.DEBUG
logging_level_stream = logging.DEBUG
jkm.jkm_postprocessing_cli.main(logging_level_file, logging_level_stream)
