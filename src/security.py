# Security-related stuff
import keyring, os
from dotenv import load_dotenv

# from .mytyping import *
import logging
log = logging.getLogger("jkm")

PROGNAME = "jkm-post"

def _get_secret_from_user(prompt:str) -> None|str:
    """Prompt user for a appsecret.
    The promp should tell users how to avoid this.

    Returns None on empty values."""
    rv = input(prompt)
    return None or str(input(prompt))
    
# Public functions
def get_cachedsecret(name:str="JKM_GOOGLE_TEMPTOKEN") -> str|None:
    "Get cached secret token from the  OS keyring."
    return keyring.get_password(PROGNAME, name)


def set_cachedsecret(value:str, name:str="JKM_GOOGLE_TEMPTOKEN") -> None:
    "Store cached secret token in the OS keyring."
    keyring.set_password(PROGNAME, name, value)

def get(name:str, prompt:str|None=None) -> None|str:
    """Get a secret value.

    Returns None on failure. """
    pw = keyring.get_password(PROGNAME, name)
    if pw is not None:
        return pw # Found a value in keyring
    else:
        log.debug(f"Secret {name} not in an OS keyring.")
    # Should we fail, try accessing an .env file
    config = load_dotenv()
    pw = os.getenv(name)
    if pw is not None:
        return pw # Found a value in .env file or a system ENV variable.
    else:
        log.debug(f"Secret {name} not in an .env file or an OS environmental variable.")
    if prompt: # as a last ask user for secret value
       return _get_secret_from_user(prompt)
    # If nothing worked, return a failure marker
    log.warning(f"Secret {name} not in any source.")
    return None

def verify_appsecret(value:str, minlen:int=20) -> bool:
    "Check if this return value looks like a valid appsecret token"
    if not value: return False # Should not be empty
    if not isinstance(value, str): return False # Must be a string
    # TODO: check length
    if len(value) < minlen: return False
    return True


