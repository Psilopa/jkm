from collections.abc import Callable, Collection, Sequence, Generator
#Examples:
#   Generator[SampleImageBase,None,None]
from typing import Self, Any, Hashable, TextIO, BinaryIO
from . import ai, sample, configfile, external
import numpy
# These need reworking!
type type_conf = configfile.tomlConfig # Depends on Python 3.12+
type type_url = str # Alias, maybe we enforce this later
type type_image = numpy.ndarray
type type_sample = sample.SampleBase
type type_sampleimage = sample.SampleImageBase
type type_airresult  = ai.AI_output
type type_rotated_rect = tuple[int,int,int,int,int]# TODO: change into rotatedrect
type type_spreadsheet = itersheets.base.WriteOnlySpreadsheet
type type_external = external.ExtBase
type type_rect= Sequence[int]

