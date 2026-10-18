from collections.abc import Callable, Collection, Sequence, Generator
#Examples:
#   Generator[SampleImageBase,None,None]
from typing import Self, Any, Hashable

type type_conf = jkm.configfile.tomlConfig # Depends on Python 3.12+
type type_url = str # Alias, maybe we enforce this later
type type_image = numpy.ndarray
type type_sample = jkm.sample.SampleBase
type type_sampleimage = jkm.sample.SampleImageBase
type type_airresult  = jkm.ai.AI_output
type type_rotated_rect = tuple[int,int,int,int,int]# TODO: change into rotatedrect
type type_spreadsheet = jkm.spreadsheet.SpreadsheetBase
type type_external = jkm.external.ExtBase
type type_rect= Sequence[int]

