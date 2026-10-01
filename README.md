# INSTALLING
* Download the code from https://github.com/Psilopa/jkm/releases
* For a basic install, run the following command in the main installation directory:
```pip install -r requirements.txt```
* For some additional options, install Python packages, if you do not have them already
```pip3 install pytesseract```
```pip3 install qreader (alternative barcode library for QR codes)```

# How JKM works under the hood
* Two modes: one that processes a directory content, and one that monitors a directory for new content
* Content to be prosessed is detected on the basis of a file name
* Once a content file has been detenced, the main look calls a Sample object constructor (type depends on the INI file)
* A sample can (and mostly should) contain one of more SampleImage objects
* Then, the main look checks for various postprocessing options as listed in the INI file
* Postprocessing is typically handled by calling a function of the Sample object (in the style of sample.getbarcodes)
* If needed, the Sample object will then look at its list of SampleImages and call their methods for extracting data from the images
* Actual processing algorithms are in separate files like jkm/barcodes.py. These typically take a image (opencv/PIL image) + 
  algorithm parameters as params.
* A custom logging classes handles logging. ALl subpacgakes should have a 'log' variable, which the main script does set.
* Sample class subclasses (etc.) should have their own _toJSON_ functions for serialization.
