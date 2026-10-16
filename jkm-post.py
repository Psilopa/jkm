# -*- coding: utf-8 -*-
from jkm.jkm_postprocessing_main import jkm_post
import logging
# For testing
import jkm.ai
jkm.ai.TESTING_BYPASS_AI_CALL = True

logging_level_file = logging.INFO
logging_level_stream = logging.INFO
jkm = jkm_post()
jkm.main(logging_level_file = logging_level_stream, logging_level_stream = logging_level_stream)

