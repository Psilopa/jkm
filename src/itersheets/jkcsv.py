# STDlib
import logging, csv, re
from pathlib import Path

# My own modules
from .errors import sheetError
from .base import new_column_action, WriteOnlySpreadsheet, ReadOnlySpreadsheet
from .mytyping import * # For type checking tools

SUFFIXES = [".csv", "csv"]
class default:
    DIALECT = csv.excel()
    QUOTING = csv.QUOTE_STRINGS
    ENCODING_ERRORS = "convert"
    ENCODING = "utf8"
    NEWLINE = ""

log = logging.getLogger() # Set from main script if fancy logging is required.
# These should go to tools (and probably replaced with better tools by someone else)
    
def sanitize_filename(text:str) -> str:
    return text
    dirty = "".join(["\\[/\\?%*:|\"<>0x7F0x00-0x1F]", chr(0x1F) * 15])
    return re.sub(text,"-",dirty) # Replace all chars in dirty with -.

class WriterCSV(WriteOnlySpreadsheet): 
    # TODO: Convert to use the DictWriter class (needs data-pre-work to handle duplicate 'keys')
    """ """
    def __init__(self:Self, filename: str|Path): 
        super().__init__(filename)
        if self.fp.suffix.lower() not in SUFFIXES: 
            raise sheetError(f"CSV output file name must end in '.csv'. {self.fp} fails")
    # ------- ABSTRACT METHOD IMPLEMENTATIONS -----------
    def _read_header(self:Self) -> tuple[str,...]:
        row = []
        with self.fp.open("r", # Append mode
                                    encoding = default.ENCODING,
                                    newline = default.NEWLINE,
                                    errors = default.ENCODING_ERRORS
                                    ) as file:
            rdr = csv.DictReader(file, dialect = self.dialect)
            fields = rdr.fieldnames
            if not fields: return tuple()
        return tuple(fields)

    def open(self:Self,
             fieldnames:Sequence[str] = tuple(), 
             dialect:csv.Dialect = default.DIALECT) -> None:
        self.dialect = dialect
        # If file exists, use first row as columns
        if not self.is_empty:
           # Get column data from existing file
           self.fields = self._read_header() + tuple(fieldnames)
        else:
            self.fields = fieldnames
        self.file = self.fp.open("a", # Append mode
                                     # SHOULD SHOULD COME FROM self.dialect?
                                    encoding = default.ENCODING,
                                    newline = default.NEWLINE,
                                    errors = default.ENCODING_ERRORS
                                    )
        self.writer = csv.DictWriter(self.file, self.fields,
                                     dialect = self.dialect,
                                     extrasaction='raise',
                                     restval = "")
        self._opened = True

    def save(self:Self) -> None:
        self._saved = False
        assert self.file, "Should not save if file has not been opened yet!"
        if self.file: self.file.flush() # Write data to file immediately
        self._saved = True

    def addrow(self:Self,
               datarowdict: dict[str,object],
               on_new_field:str = new_column_action.NEWFILE
               ) -> None:
        if not self.is_open:
            raise sheetError(f"Trying to write into {self.fp} after closing the file.")        
        if self.is_empty:
            self.writeheader()
        diff = self.lacks_columns(datarowdict.keys() )        
        if diff: 
            log.warning(f"Missing column(s): {", ".join(diff)}.")
            if on_new_field == new_column_action.NEWFILE:
                if not self.is_empty: # Not an empty file, need to create a backup
                    oldname = self.fp.stem
                    newname = self.fp.with_stem(str(oldname) +"_no_"+ "_".join(diff) )
                    newname = sanitize_filename(newname)
                    log.warning(f"Moving old file to {newname}.")
                    self.move(newname, overwrite = True)
                self.close()
                self.fields = self.fields + tuple(diff)
                log.warning(f"Entering new data to {self.filename}.")
                self.open(fieldnames = self.fields) # Reopen as a new file
                # Force header writing
                self.writeheader()
            else:
                raise sheetError(f"New column name, but no given way of adding columns specified. WriterCSV supports only swapping to a new file for now.")
        self.writer.writerow(  datarowdict )
        self.save()
        
    def writeheader(self:Self) -> None:
        # TODO: ERROR STATE HANDLING
        if not self.is_empty: pass # Do not write a header if file already has material in it
        self._saved = False
        # Can update  self.writer.fieldnames as long as header has not yet been written.
        self.writer.writeheader()
        assert self.file, "Should not save if file has not been opened yet!"
        if self.file: self.file.flush() # Write data to file immediately
        self._saved = True


class ReaderCSV(ReadOnlySpreadsheet):
    # ------- ABSTRACT METHOD IMPLEMENTATIONS -----------
    def __init__(self:Self,
                 filename: str|Path,
                 dialect:csv.Dialect = default.DIALECT): 
        super().__init__(filename)
        self.dialect = dialect
        if self.fp.suffix not in SUFFIXES: 
            raise sheetError(f"CSV output file name must end in '.csv'. {self.fp} fails")

    def open(self:Self) -> None:
        if not self.exists:
            raise sheetError(f"Coulf not access file {self.fp}.")
        self.file = self.fp.open("r",
                                     # SHOULD SHOULD COME FROM self.dialect?
                                    encoding = default.ENCODING,
                                    newline = "",
                                    errors = default.ENCODING_ERRORS
                                    )
        self.reader = csv.DictReader(self.file,
                                    delimiter = ",",
                                     dialect = self.dialect,
                                     restval="" # Value if cell is empty
                                     )
        self._opened = True

    def next(self:Self) -> csv.DictReader[str]: 
        return self.reader # Next in sequence as a dictionary

    @property
    def fields(self:Self) -> tuple[str,...]:
        rv = self.reader.fieldnames
        return tuple(self.reader.fieldnames or []) # Make sure the return value is a list, self.reader.fieldnames can return None
    # Has no setter: we are reading only...
