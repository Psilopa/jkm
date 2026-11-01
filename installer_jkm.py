#!/usr/bin/python
# -*- coding: utf-8 -*-

# Install pyxls
# NOTE: THE INSTALLER ITSELF SHOULD USE NOTHING OUTSIDE STDLIB
import subprocess, sys, glob, re, argparse, importlib
from pathlib import Path
_TEST = False # Bypass pip for speed
pythonpath = Path(sys.executable).parent

batfiles = glob.glob("batsrc/*.bat")
installdir = Path(__file__).parent # The directory where the installer is
configdir = installdir / Path("setup")
sourcefile = installdir / "jkm-post.py"

def install_packages():
    if _TEST: return
    reqfile = "requirements.txt"
    print(f"Trying to install a Python modules from file {reqfile}")
    rv = subprocess.run([sys.executable, "-m", "pip", "install", "-r", reqfile])
    try:
        rv.check_returncode()
        print(f"\tInstalled {reqfile} successfull.")
    except subprocess.CalledProcessError as msg:
        print(f"\tInstall {reqfile} failed with error message. Exiting.")
        sys.exit()


def install_jkm_post():
    install_packages( )  

    # TODO: THESE DEPEND ON THE PATHS NOTING HAVING EMPTY SPACES!
    re_pythonexe = re.compile( r'"\S*?\.exe"' )
    re_sourcefile = re.compile( r'"\S*?\.py"' )
    re_configfile = re.compile( r'"\S*?\.toml"' )
    # Copy and update BAT files
    for fn in [Path(x) for x in batfiles]:
         outfp = installdir / fn.with_suffix(".bat").name # Destination name
         print("Creating BAT file from template: ", outfp)
         with fn.open("r") as f: d = f.read()
         # Path to main script
         newsource = '"' + str( sourcefile) + '"'
         newsource = newsource.replace( "\\", "/" )
         d = re_sourcefile.sub(newsource, d)
         # Path to  python itself
         newpythonpath = '"' + str(sys.executable) + '"'
         newpythonpath = newpythonpath.replace( "pythonw.exe", "python.exe" ) 
         newpythonpath = newpythonpath.replace( "\\", "/" ) 
         # Path to configfile
         m = re_configfile.search(d)
         if m:             
            oldconfpath = Path(m[0][1:-1]) # Strip ""
            newconfpath =  '"' + str( configdir / oldconfpath.name) + '"'
            newconfpath = newconfpath.replace( "\\", "/" ) 
            d = re_configfile.sub(newconfpath, d)
         d,n = re_pythonexe.subn(newpythonpath, d)
         with outfp.open("w") as outfile: outfile.write(d)

if __name__ == '__main__':
    install_jkm_post()
