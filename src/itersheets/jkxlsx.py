# STDlib
import logging
from pathlib import Path

# Non-stdlib
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

# My own modules
from .errors import sheetError
from .base import ReadOnlySpreadsheet
#from .mytyping import * # For type checking tools

log = logging.getLogger() # Set from main script if fancy logging is required.

class XLSXFile():
    FORMAT_NAME = "Excel"
    SUFFIXES = [".xlsx", "xlsx"]
    BOLDFONT = Font(bold=True)
    def __init__(self:Self):
        self._format_reset()

    def _format_reset(self:Self):
        self.wb = None
        self.ws = None # ODS Table  equivalent
        
    def format_read_header(self:Self, filepath:Path) -> tuple:
        wb = load_workbook(filepath)
        assert wb, "wb should exist when we try to read a row in format_read_header()."
        ws = wb.active
        assert ws, "ws should exist when we try to read a row in format_read_header()."
        rv = tuple(x.value for x in ws[1:1])
        wb.close()
        return rv

    def format_open(self:Self, filepath: Path):
        if not filepath.exists(): # TODO: test for readable.
            raise sheetError(f"File {filepath} does not exist or is unavailable.")
        self.wb = load_workbook(filepath)        
        if not self.wb:
            raise sheetError(f"Could not open file {filepath}")
        self.ws = self.wb.active

    def format_create(self:Self):
        self.wb = Workbook()
        assert self.wb, "wb should exist when we try to read a row in format_create()."
        self.ws = self.wb.active

    def format_map_fields_to_columns(self:Self, fields:type_fields):
        return { k:v for k,v in zip(fields, range(len(fields))) } 
    
    def format_add_row( self:Self, values:Sequence ):
        assert self.ws, "self.ws sould exist when we try to addrow()."
        self.ws.append( tuple(values) )

    def format_get_row_values(self:Self, nrow:int) -> tuple:
        assert self.ws, "self.ws sould exist when we try to get row values."
        return tuple(x.value for x in self.ws[nrow+1:nrow+1])

    def format_set_row_values(self:Self, nrow:int, values:Sequence) -> None:
        max_col = len(values)
        assert self.ws, "self.ws sould exist when we try to writeheader()."
        for i in range(max_col):# 1-based indexing in Excel
            cell = self.ws.cell(row= nrow+1, column = i+1, value= values[i])
                
    def format_set_row_font(self:Self, nrow:int, font):
        assert self.ws, "self.ws sould exist when we try to writeheader()."
        for cell in self.ws[nrow+1:nrow+1]:# 1-based indexing in Excel
            cell.font = font

    def format_save(self:Self, filepath:Path) -> None:
        # TODO: ERROR HANDLING ON BAD PATH
        if self.wb: self.wb.save(filepath)

    def format_close(self:Self, filepath:Path|None=None) -> None:
        if self.wb and filepath:
            self.format_save(filepath)
        if self.wb:
            self.wb.close()
        self._format_reset()

    def iterator_values(self:Self):
        assert self.ws, "self.ws sould exist when we try to read values from it."
        return self.ws.values


