# INSTALLING
* Install Python. Current development and the installer script are designed for Python 3.14, but anything newer than 3.7 might work if you install the dependencies listed in requirements.txt by hand.
* Download the code from https://github.com/Psilopa/jkm/releases
* For a basic install, run the following command in the main installation directory:
```pip install -r requirements.txt```
* For some additional options, install Python packages, if you do not have them already
```pip3 install pytesseract```
```pip3 install qreader (alternative barcode library for QR codes)```
* Make a copy of one of the example configuration files in setup/ and chance the directories etc. to match your system
* If you use the AI-based systems, see  AUTHENTICATION.md
* If you are on MS Windows, copy and edit one of the provided .BAT files to match your system. These allow a click to start setup.
* As jkm-post uses a large third-party package (google.genai) with many dependencies, the security conscious solution is to run it in a more or less walled environment: a Python venv, a Docker container, a full virtual machine, or whatever fits your fancy. 

# USING jkm-post
Once the system is set up and working (se Installation), running it is a simple as clicking on a BAT file (on windows) or entering a command in a command prompt:
```python jkm-post.py -c setup/my_conf_file.toml```.

On some systems, you might need to use python3 as the intepreter name.

Jkm-post has two modes: one that processes a directory content, and one that monitors a directory for new content.

Content to be processed is detected on the basis of a file name as specified in the configuration file section _data:recognize_by_filename_pattern_. Four types are currently supported: 
* SINGLEFILE. The triggering file is treated as the Sample.
* IMAGEDIR. Builds a Sample from all images matching the _data:recognize_by_filename_pattern_ pattern in the directory 
* MZH_INSECTLINE. Uses data from a directory (containing two pictures and metadata) to construct a sample. For the Finnish Museum of Natural History, and as an example of a more complicated Sample with metadata file output.
* MZH_PLANTLINE. Uses data from a directory (containing a picture and metadata) to construct a sample. For the Finnish Museum of Natural History.

# How jkm-post works under the hood
* Once a content file has been detected, the main look calls a Sample object constructor (type depends on the config file value _data:datatype_to_load_)
* If you want to adapt the system for your institure and need a more complicated setup than SINGLEFILE and IMAGEDIR allow for, these are the main parts of the code you need to edit:
** _jkm.sample.py_. This is were Sample classes are defined. Sample classes are children of SampleEvent- For a simple example, see SingleImageSample. 
** **Sample classes should declare their capabilities through _supports_rename_files_ -style object property variables. See SampleBase for the list of available options. Add your own if you modify the code).**
** _jkm.jkm_postprocessing_cli.processSingleEvent_. Here we call the staticmethod constructor like SingleImageSample.from_image_file() of the Sample classes to generate a sample. Add your own.
* A sample can (and mostly should) contain one of more SampleImage (or subclass) objects.
* Then, the main look checks for various postprocessing tasks as listed in the TOML file.
* Postprocessing task functions should be named task_*. Example: task_write_spreadsheet.
* Postprocessing is often handled by calling a function of the Sample object in the style of task_add_prefix_to_imagefiles just calling sample.add_prefix_to_imagefiles().
* If needed, the Sample object will then look at its list of SampleImages and call their methods for extracting data from the images.
* Actual processing algorithms are in separate files like jkm/barcodes.py. These typically take a image (opencv/PIL image) + algorithm parameters as params and are more of less independent of jkm.
* A custom logging classes handles logging. ALL jkm packages should have a 'log' variable, which the main script should set.
* Sample class subclasses (etc.) should have their own _toJSON_ functions for serialization. Using jsonpickle to serialize arbitrary data can be useful here.

DEV OPTIONS
* jkm.ai has a _TESTING_BYPASS_AI_CALL option to use hardcoded AI output rather than actually propting the AI (note: this needs updating if the AI output format changes)"
<<<<<<< HEAD
* Debug-level logging can be turned on and off from jkm-post.py.
=======
* Debug-level logging can be turned on and off from jkm-post.py.
>>>>>>> 4887c5bd7ebbfc948a8a5ddbfaaf94d2268c7078
