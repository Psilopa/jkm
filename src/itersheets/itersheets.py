# Expose main classes
from .writer import WriterXLSX, WriterODS, log as writerlog 
from .reader import ReaderXLSX, ReaderODS
from .jkcsv import WriterCSV, ReaderCSV
from .base import new_column_action, log as baselog 

# Connect all log objects 
log = writerlog = baselog 

