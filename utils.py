import io
import logging
import os
import pathlib
import sys

import requests
from google.api_core import exceptions
from google.cloud import vision
from PIL import Image, ImageDraw

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


def trim(s):
    """Recursively get s under 1500 bytes by dividing it in half."""
    if sys.getsizeof(s) < 1500:
        return s
    return trim(s[:int(len(s)/2)])


def name_from_path(filepath):
    """Given str 'path/to/assets/name.jpg', returns 'name'."""
    return filepath.split("/")[-1][:-4]


def vision_img_from_path(v_client, filepath):
    """Given a JPG location to open, returns Google Cloud Vision Image object.
    
    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        filepath (str): 'path/to/assets/name.jpg'
    
    Returns:
        google.cloud.vision_v1.types.Image
    """
    logger.debug(f"Opening {filepath}...")
    with io.open(filepath, 'rb') as image_file:
        content = image_file.read()
    image = vision.types.Image(content=content)
    return image


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

################################################################################
def draw_on_box(box, filepath):
    """Given a list of coordinates and a JPG location to open, draws box and
    saves as new file.
    
    Args:
        box (list): Integer coordinates of polygon vertices. Example: [392, 353,
        542, 353, 542, 470, 392, 470]
        filepath (str): 'path/to/assets/name.jpg'
    
    Returns:
        str: path to new file
    """
    # https://cloud.google.com/vision/docs/crop-hints
    if not os.path.exists("assets/cropped"):
        pathlib.Path("assets/cropped").mkdir(parents=True)
    name = name_from_path(filepath)
    draw_path = os.path.join(os.path.dirname(__file__), f'assets/cropped/{name}_boxed.jpg')
    with Image.open(filepath) as im:
        # Don't draw on original.
        with im.copy() as im2:
            draw = ImageDraw.Draw(im2)
            draw.polygon(xy=box,
                         fill=None,
                         outline='red')
            im2.save(draw_path, 'JPEG')
    return draw_path


def crop_to_box(box, filepath):
    """Given a list of points and a JPG location to open, draws crops to points
    and saves as new file.
    
    Args:
        box (list): Integer points of box. Example: [392, 353, 542, 470]
        filepath (str): 'path/to/assets/name.jpg'
    
    Returns:
        str: path to new file
    """
    if not os.path.exists("assets/cropped"):
        pathlib.Path("assets/cropped").mkdir(parents=True)
    name = name_from_path(filepath)
    crop_path = os.path.join(os.path.dirname(__file__), f'assets/cropped/{name}_cropped.jpg')
    with Image.open(filepath) as im:
        with im.crop(box=box) as im2:
            im2.save(crop_path, 'JPEG')
    return crop_path


def get_safety_annotations(v_client, image):
    # TODO: Change signature to match get_object_annotations and get_label_annotations.
    """
    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        image (google.cloud.vision_v1.types.Image

    Returns:
        dict of likelihoods that image contains an unsafe category:
        {'adult': 'VERY_UNLIKELY', 'medical': 'UNLIKELY', 'spoofed': 'POSSIBLE',
         'violence': 'LIKELY', 'racy': 'VERY_LIKELY'}
    """
    # https://cloud.google.com/vision/docs/detecting-safe-search
    response = v_client.safe_search_detection(image=image)
    logger.debug(f"API response for safe_search_detection: {response}")
    if not response.safe_search_annotation:
        logger.error(f"No safety annotations for image.")
        raise exceptions.GoogleAPIError(f"No safety annotations for image. Vision API response: {response}")
    likelihood_name = ('UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE',
                       'LIKELY', 'VERY_LIKELY')
    safety_annotations = {"adult": likelihood_name[response.safe_search_annotation.adult],
                          "medical": likelihood_name[response.safe_search_annotation.medical],
                          "spoofed": likelihood_name[response.safe_search_annotation.spoof],
                          "violence": likelihood_name[response.safe_search_annotation.violence],
                          "racy": likelihood_name[response.safe_search_annotation.racy]}
    logger.debug(f"Returning safety_annotations: {safety_annotations}")
    return safety_annotations


def get_label_annotations(v_client, filepath):
    """Given a JPG location to open, retrieves image's label annotations.

    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        filepath (str): 'path/to/assets/name.jpg'

    Returns:
        list of str labels that describe image contents: ['Bird', 'Soil', 'Lark']
    """
    # https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#EntityAnnotation
    image = vision_img_from_path(v_client, filepath)
    response = v_client.label_detection(image=image)
    logger.debug(f"API response for label_detection: {response}")
    if not response.label_annotations:
        logger.error(f"No label annotations for image.")
        raise exceptions.GoogleAPIError(f"No label annotations for image. Vision API response: {response}")
    labels = list(l.description for l in response.label_annotations)
    logger.debug(f"Returning label annotations: {labels}")
    return labels


def get_object_annotations(v_client, filepath):
    """Given a JPG location to open, return information about objects detected
    in the image.

    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        filepath (str): 'path/to/assets/name.jpg'
    
    Returns:
        list of object annotation dictionaries with object name and box
        dimensions:
        [{'name': 'bird', 'crop_box': [392, 353, 542, 470], 'draw_box': [392,
        353, 542, 353, 542, 470, 392, 470]},
         {'name': 'animal', 'crop_box': [392, 353, 542, 470], 'draw_box': [392,
        353, 542, 353, 542, 470, 392, 470]}]
    """
    # https://cloud.google.com/vision/docs/detecting-objects
    image = vision_img_from_path(v_client, filepath)
    response = v_client.object_localization(image=image)
    logger.debug(f"Response for {filepath} object_localization request: {response}")
    if not response.localized_object_annotations:
        logger.error(f"No object annotations for {filepath}.")
        raise exceptions.GoogleAPIError(f"No object annotations for {filepath}. Vision API response: {response}") 
    width, height = Image.open(filepath).size
    object_annotations = list()
    for o in response.localized_object_annotations:
        oa = dict()
        verts = o.bounding_poly.normalized_vertices
        oa["name"] = o.name.lower()
        # https://pillow.readthedocs.io/en/5.3.x/reference/Image.html#PIL.Image.Image.crop
        oa["crop_box"] = [round(verts[0].x * width),   # left
                          round(verts[0].y * height),  # upper
                          round(verts[2].x * width),   # right
                          round(verts[2].y * height)]  # lower
        # https://pillow.readthedocs.io/en/5.3.x/reference/ImageDraw.html#PIL.ImageDraw.PIL.ImageDraw.ImageDraw.polygon
        oa["draw_box"] = [round(verts[0].x * width), round(verts[0].y * height),
                          round(verts[1].x * width), round(verts[1].y * height),
                          round(verts[2].x * width), round(verts[2].y * height),
                          round(verts[3].x * width), round(verts[3].y * height)]
        object_annotations.append(oa)
    logger.debug(f"Returning object annotations: {object_annotations}")
    return object_annotations


def get_crop_hints(v_client, filepath):
    """Given a JPG location to open, retrieves vertices to crop to.

    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        filepath (str): 'path/to/assets/name.jpg'
    
    Returns:
        list-esque google.protobuf.internal.containers.RepeatedCompositeFieldContainer
        of four google.cloud.vision_v1.types.Vertex objects. Individual points
        can be accessed like:
            verts[0].x, verts[0].y,
            verts[1].x, verts[1].y,
            verts[2].x, verts[2].y,
            verts[3].x, verts[3].y
    """
    # https://cloud.google.com/vision/docs/crop-hints
    image = vision_img_from_path(v_client, filepath)
    response = v_client.crop_hints(image=image)
    logger.debug(f"API response for crop_hints: {response}")
    if not response.crop_hints_annotation:
        logger.error(f"No crop hints annotation for image.")
        raise exceptions.GoogleAPIError(f"No object annotations for image. Vision API response: {response}")
    hints = response.crop_hints_annotation.crop_hints
    vertices = hints[0].bounding_poly.vertices
    logger.debug(f"Returning crop hints bounding poly vertices: {vertices}")
    return vertices


def is_safe(safety_annotations):
    """Returns False if it is likely or very likey that the image contains
    questionable content. Otherwise, returns True.
    
    Args:
        safety_annotations (dict)

    Returns:
        bool
    """
    return all(x not in safety_annotations.values() for x in ["LIKELY", "VERY_LIKELY"])
