# STDlib
import logging
from pathlib import Path

# My own modules
from .jkods import ODSFile
from .jkxlsx import XLSXFile
from .errors import sheetError
from .base import new_column_action, WriteOnlySpreadsheet
#from .mytyping import * # For type checking tools

log = logging.getLogger() # Set from main script if fancy logging is required.
def unique(s: Sequence) ->tuple[str,...] :return tuple(dict.fromkeys(s)) 
# -------------- Shared code for XLSX and ODS implementation --------------
class WriterBase(WriteOnlySpreadsheet):
    def __init__(self:Self, filename: str|Path): 
        super().__init__(filename)
        self.field2col = {} # Maps column name to column number
        if self.fp.suffix.lower() not in self.SUFFIXES: 
            raise sheetError(f"{self.FORMAT_NAME} output file name must end in {self.SUFFIXES[0]}. {self.fp} fails")

    # BASE ABSTRACT METHOD IMPLEMENTATIONS
    def open(self:Self,
             fieldnames:Sequence[str] = tuple()
             ) -> None:
        self._reset()
        # If file exists, use first row as columns
        if not self.is_empty:
            self.format_open(self.fp)
            self.fields = self.format_read_header(self.fp) + tuple(fieldnames)
        else:
            self.format_create()
            self.fields = fieldnames
        # Map field name to column number (0-based indexing as we do not use this numbering directly in Excel)
        self.field2col = self.format_map_fields_to_columns(self.fields)
        self._opened = True

    def _reset(self:Self):
        self._opened = False
        self.wb = None        
        self.fields = tuple()
        self.field2col = {} # Maps column name to column number

    def save(self:Self) -> None:
        self._saved = False
        self.format_save(self.fp)
        self._saved = True

    def addrow(self:Self,
               datarowdict: dict[str,object],
               on_new_field:str
               ) -> None:
        self._saved = False
        if not self.is_open:
            raise sheetError(f"Trying to write into {self.fp} after closing the file.")        
        if self.is_empty:
            self.writeheader()
        diff = self.lacks_columns( datarowdict.keys() )
        if diff: 
            log.warning(f"Missing column(s): {", ".join(diff)}.")
            if on_new_field == new_column_action.INSERT:
                log.info(f"Inserting new columns: {", ".join(diff)} into {self.filename}.")
                self.fields = self.fields + tuple(diff)
                self.field2col = { k:v for k,v in zip(self.fields, range(len(self.fields))) } 
                # Need to rewrite header line
                self.writeheader()
            else:
                sheetError(f"New column name, but no given way of adding columns specified.")
        outrow = [""]*len(self.fields)
        for colname,value in datarowdict.items():
            pos = self.field2col[colname]
            outrow[pos] = str(value) if value else ""
        self.format_add_row(outrow)
        self.save() # Saving after each insert if quite heavy

    def writeheader(self:Self) -> None:
        self._saved = False
        assert self.wb, "self.wb sould exist when we try to writeheader()."
        if self.is_empty: # Empty file, we need to add a row 
            self.format_add_row(self.fields)
            if self.BOLDFONT: self.format_set_row_font(0, self.BOLDFONT)
        else: # Update existing header line
            self.format_set_row_values(0, self.fields)
            self.format_set_row_font(0, self.BOLDFONT)
        # Do not save just for a header, wait for a data row

    def close(self, save:bool = True) -> None:
        if save and self.wb: self.save()
        if not self._saved: log.warning(f"Closing file {self.filename} without saving first.")
        self._reset()

#------------------ EXCEL SPECIFIC STUFF -------------
class WriterXLSX(WriterBase, XLSXFile): 
    pass
#------------------ ODS SPECIFIC STUFF -------------
class WriterODS(WriterBase, ODSFile): 
    pass
