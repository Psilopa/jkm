import toml
from pathlib import Path
#from importlib.metadata import version
# TODO: PARSE FROM pyproject.toml
pyproject_toml_file = Path(__file__).parent.parent / "pyproject.toml"

class MetaError(Exception): pass

try:
    # TODO: should fail with an exception
    meta = toml.load(pyproject_toml_file)

    # Assumes these exist
    name = meta['project']['name']
    description = meta['project']['description']
    authors = ",".join ( x['name'] for x in meta['project']['authors'] )
    my_license = "" # license is reserved in Python
    version = meta['project']['version']
    nameversion = f"{name} ({version})"
    about = f"""
    {name} {version} is a {description}
    Creator(s): {authors}.

    Usage: 
    python3 {name} path_to-settings"""
except (FileNotFoundError, KeyError) as msg:
    raise MetaError(msg)
