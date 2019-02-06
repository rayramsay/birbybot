#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import json
import logging
import os
import pathlib
import sys

import requests
from google.api_core import exceptions
from google.cloud import datastore
from google.cloud import vision
from PIL import Image, ImageDraw

import utils
from flickr_to_datastore import write_entities_to_datastore

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
utils.configure_logger(logger, console_output=True)
################################################################################

def pull(ds_client, kind, key, val):
    """Retrieves entities from datastore where key == val.

    Args:
        ds_client (google.cloud.datastore.client.Client)
        kind (str): e.g., "Photo"
        key (str): e.g., "is_classified"
        val (bool): e.g., False

    Returns:
        list of google.cloud.datastore.entity.Entity of kind 'Photo': 
        [<Entity('Photo', 'Flickr-36092472285') {'source': 'Flickr',
        'is_classified': 'False', ...}>, ...]
    """
    query = ds_client.query(kind=kind)
    query.add_filter(key, "=", val)
    logger.debug("Retrieving unclassified entities...")
    entities = list(query.fetch())
    logger.info(f"Retrieved {len(entities)} {kind} entities where {key} is {val}.")
    logger.debug(entities)
    return entities


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


def is_bird(labels):
    """Given a list of strings, returns True if any match."""
    return any(x in labels for x in ["bird", "seabird", "beak", "egg"])


def classify_entity(v_client, entity):
    """Classifies entity as bird (and therefore as classified), and updates
    entity locally.

    Args:
        v_client (google.cloud.vision_v1.ImageAnnotatorClient)
        entity: google.cloud.datastore.entity.Entity of kind 'Photo'
    
    Returns:
        None
    """
    def too_big(blob):
        return sys.getsizeof(blob) > 1500

    name = entity.key.name
    # Download from URL.
    filepath = utils.download_image(url=entity.get("download_url"),
                              name=name)
    # Find objects in image.
    logger.debug(f"Requesting object detection for {filepath}...")
    obs = None
    try:
        obs = get_object_annotations(v_client, filepath)
        object_names = list(o["name"].lower() for o in obs)

        # TODO: Truncate smarter in order to prevent
        # google.api_core.exceptions.InvalidArgument: 400 The value of property
        # is longer than 1500 bytes.
        if too_big(json.dumps(obs)):
            logger.warn(f"Object annotation {obs} too long to save to datastore; truncating...")
            obs = obs[:100]
        entity.update({
            "object_labels": json.dumps(obs),
            "is_bird": is_bird(object_names)
        })
        logger.debug(f"First pass: {name} is_bird = {entity.get('is_bird')}")
    except exceptions.GoogleAPIError as e:
        logger.exception(e)

    # Double check non-bird.
    if not entity.get("is_bird") == True:
        try:
            # If we have crop_boxes, crop and annotate.
            if obs:
                label_annotations = list()
                for o in obs:
                    draw_box = o["draw_box"]
                    draw_path = draw_on_box(box=draw_box, filepath=filepath)
                    crop_box = o["crop_box"]
                    crop_path = crop_to_box(box=crop_box, filepath=filepath)
                    la = get_label_annotations(v_client, crop_path)
                    label_annotations.extend(la)
                    # If we've found a bird, stop iterating through objects.
                    if is_bird(la):
                        break
            # If no boxes, annotate the whole image.
            else:
                label_annotations = get_label_annotations(v_client, filepath)
            
            # TODO Before dumping and updating label_annotations, check for bigness.
            entity.update({
                "vision_labels": json.dumps(label_annotations),
                "is_bird": is_bird(label_annotations)
            })
            logger.debug(f"Second pass: {entity.key.name} is_bird = {entity.get('is_bird')}")
        except exceptions.GoogleAPIError:
            pass
    
    # Move non-birds to different folder so that they are easier to manually review.
    if entity.get("is_bird") == False:
        if not os.path.exists("assets/negative"):
            pathlib.Path("assets/negative").mkdir(parents=True)
        neg_path = os.path.join(os.path.dirname(__file__), f'assets/negative/{name}.jpg')
        logger.debug(f"Moving from {filepath} to {neg_path}")
        os.rename(filepath, neg_path)

    if entity.get("is_bird") != None:
        entity.update({"is_classified": True})
    logger.debug(entity)
    return


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


def classify_unclassified_entities(ds_client, v_client):
    entities = pull(ds_client,
                    kind="Photo",
                    key="is_classified",
                    val=False)
    if entities:
        classified = 0
        non_birds = 0
        for entity in entities:
            logger.debug(f"Classifying {entity.key.name}...")
            classify_entity(v_client, entity)
            logger.debug(f"Saving {entity.key.name} in datastore...")
            ds_client.put(entity)
            if entity.get("is_classified") == True: classified += 1
            if entity.get("is_bird") == False: non_birds += 1
        logger.info(f"Classified and updated {classified} entities.")
        logger.warning(f"{non_birds} entities were classified as not birds.")
        logger.warning(f"{(len(entities) - classified)} entities were not classified.")
    return

################################################################################
if __name__ == "__main__":
    filename = os.path.basename(__file__)
    logger.info(f"Starting {filename}...")
    try:
        ds_client = datastore.Client()
        v_client = vision.ImageAnnotatorClient()
        classify_unclassified_entities(ds_client, v_client)
        logger.info(f"Finished {filename}.")
    except Exception as e:
        logger.exception(e)
