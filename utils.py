import logging
import os

def chunk(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

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
