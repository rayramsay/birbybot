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

def pull_unclassified_entities(ds_client):
    # TODO: Update docstring
    """Retrieves entities from datastore that have no value for vision_labels.

    Args:
        ds_client (google.cloud.datastore.client.Client)

    Returns:
        list of google.cloud.datastore.entity.Entity of kind 'Photo'
    """
    query = ds_client.query(kind="Photo")
    query.add_filter("is_classified", "=", False)
    logger.debug("Retrieving unclassified entities...")
    entities = list(query.fetch())
    logger.info(f"Retrieved {len(entities)} unclassified entities.")
    logger.debug(entities)
    return entities


def pull_non_birds(ds_client):
    # TODO: Update docstring
    """
    Args:
        ds_client (google.cloud.datastore.client.Client)

    Returns:
        list of google.cloud.datastore.entity.Entity of kind 'Photo'
    """
    query = ds_client.query(kind="Photo")
    query.add_filter("is_bird", "=", False)
    logger.debug("Retrieving non-bird entities...")
    entities = list(query.fetch())
    logger.info(f"Retrieved {len(entities)} non-bird entities.")
    logger.debug(entities)
    return entities


def download_image(url, name):
    # TODO: Improve docstring
    """Downloads image from url, saves, returns filepath.
    
    Returns:
        str 
    """
    if not os.path.exists("assets"):
        pathlib.Path("assets").mkdir(parents=True)
    filepath = os.path.join(os.path.dirname(__file__), f'assets/{name}.jpg')
    logger.debug(filepath)
    
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


def name_from_path(filepath):
    return filepath.split("/")[-1][:-4]


def too_big(blob):
    return sys.getsizeof(blob) > 1500


def vision_img_from_path(v_client, filepath):
    # TODO: Docstring
    """
    Args
    filepath (str)
    Returns: google.cloud.vision_v1.types.Image
    """
    logger.debug(f"Opening {filepath}...")
    with io.open(filepath, 'rb') as image_file:
        content = image_file.read()
    image = vision.types.Image(content=content)
    return image


def get_safety_annotations(v_client, image):
    # TODO: Docstring
    """ arg google.cloud.vision_v1.types.Image"""
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
    # TODO: Improve docstring
    """Retrieve image's label annotations from Cloud Vision API.

    Arg: google.cloud.vision_v1.types.Image

    Returns:
        labels (list): List of EntityAnnotation objects. E.g., [mid: "/m/02mhj"
        description: "ecosystem" score: 0.9368894100189209 topicality: 0.9368894100189209, ...]
        See https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#EntityAnnotation
    """
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
    # TODO: Docstring
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
    questionable content.
    
    Args:
        safety_annotations (dict)

    Returns:
        bool
    """
    return all(x not in safety_annotations.values() for x in ["LIKELY", "VERY_LIKELY"])


def is_bird(labels):
    # TODO Docstring
    """l_a list"""
    return any(x in labels for x in ["bird", "seabird", "beak", "egg"])


def classify_entity(v_client, entity):
    # TODO: Docstring
    """
    """
    name = entity.key.name
    # Download from URL.
    filepath = download_image(url=entity.get("download_url"),
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
            obs = obs[:1]
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
            # If no boxes, annotate whole image.
            else:
                label_annotations = get_label_annotations(v_client, filepath)
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
    # TODO: Docstring
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
    # TODO: Docstring
    im = Image.open(filepath)
    im2 = im.crop(box=box)
    if not os.path.exists("assets/cropped"):
        pathlib.Path("assets/cropped").mkdir(parents=True)
    name = name_from_path(filepath)
    crop_path = os.path.join(os.path.dirname(__file__), f'assets/cropped/{name}_cropped.jpg')
    im2.save(crop_path, 'JPEG')
    return crop_path


def classify_unclassified_entities(ds_client, v_client):
    entities = pull_unclassified_entities(ds_client)
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
