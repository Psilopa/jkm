#INSTALLING
* Download the code from https://github.com/Psilopa/jkm/releases
* For a basic install, run the following command in the main installation directory:
```pip install -r requirements.txt```
* For some additional options, install Python packages, if you do not have them already
```pip3 install pytesseract```
```pip3 install qreader (alternative barcode library for QR codes)```

USING AN UPDATING CSV FILE AS A DATA SOURCE IN EXCEL (TODO)
-----------------------------------------------------------
Excel files are in principle editable only by one program at a time. We can get around this limitation by having one file open normally in Excel, another one as a read-only updating data source, and pulling data from the latter into the former via VLOOKUP. This is a bit untrivial :/
