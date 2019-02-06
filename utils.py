import logging
import os
import pathlib

import requests

### LOGGING ####################################################################
def configure_logger(logger, console_output=False):
    logger.setLevel(logging.DEBUG)
    path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    fh = logging.FileHandler(os.path.join(path, "birbybot.log"))
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(module)s | %(funcName)s | %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    if console_output:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

logger = logging.getLogger(__name__)
configure_logger(logger, console_output=True)
################################################################################

def chunk(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def download_image(url, name):
    # TODO: Handle other filetypes than JPG?
    """Downloads image from url, saves to disk, returns filepath.

    Args:
        url (str): URL of image
        name (str): Name to save file as (do not include extension)
    
    Returns:
        str: e.g., "path/to/assets/name.jpg"
    """
    if not os.path.exists("assets"):
        pathlib.Path("assets").mkdir(parents=True)
    filepath = os.path.join(os.path.dirname(__file__), f'assets/{name}.jpg')
    
    # If we've already downloaded an image, just return.
    if os.path.exists(filepath):
        logger.debug(f"{filepath} already exists.")
        return filepath
    
    logger.debug(f"Opening {url}...")
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(filepath, 'wb') as image:
            for chunk in r:
                image.write(chunk)
        logger.debug(f"Saved image as {filepath}")
    else:
        logger.error(f"Failed to download {name} from {url}")
        r.raise_for_status()
    return filepath