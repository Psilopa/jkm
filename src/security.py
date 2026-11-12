# Security-related stuff
import keyring, os
from dotenv import load_dotenv

# from .mytyping import *
import logging
log = logging.getLogger("jkm")

def _get_secret_from_user(prompt):
    """Prompt user for a appsecret.
    The promp should tell users how to avoid this.

    Returns None on empty values."""
    rv = input(prompt)
    return None or input(prompt)
    
# Public functions
def get_cachedsecret(name="jkm_cached_token"):
    return keyring.get_password("jkm", name)
    "Get cached secret token from the  OS keyring."

def set_cachedsecret(value, name="jkm_cached_token"):
    "Store cached secret token in the OS keyring."
    keyring.set_password("jkm", name, value)

def get(name, prompt=None):
    """Get a secret value.

    Returns None on failure. """
    pw = keyring.get_password("jkm-post", name)
    if pw is not None:
        log.debug(f"Secret {name} found in an OS keyring.")
        return pw # Found a value in keyring
    else:
        log.info(f"Secret {name} not in an OS keyring.")
    # Should we fail, try accessing an .env file
    config = load_dotenv()
    pw = os.getenv(name)
    if pw is not None:
        log.debug(f"Secret {name} found in an .env file or an OS environmental variable.")
        return pw # Found a value in .env file or a system ENV variable.
    else:
        log.info(f"Secret {name} not in an .env file or an OS environmental variable.")
    if prompt: # as a last ask user for secret value
       return _get_secret_from_user(prompt)
    # If nothing worked, return a failure marker
    log.warning(f"Secret {name} not in any source.")
    return None

def verify_appsecret(value:str, minlen=20) -> bool:
    "Check if this return value looks like a valid appsecret token"
    if not value: return False # Should not be empty
    if not isinstance(value, str): return False # Must be a string
    # TODO: check length
    if len(value) < minlen: return False
    return True

if __name__ == '__main__':
    apptoken = get_appsecret("Missing an jkm app secret token string. This is needed for the AI call. Please provide one. See jkm/DOC/AUTHENTICATION.md for details about how you can get one (and how to avoid this question),")
    print(f"Apptoken returned '{apptoken}'")
    print("Verification return", verify_appsecret(apptoken) )
    
