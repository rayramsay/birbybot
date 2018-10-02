#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: Refactor to preserve access to image information (width)
# Get vertexes from detect images

import datetime
import io
import json
import logging
import os
import pathlib
import random
import sys

import requests
from google.api_core import exceptions
from google.cloud import datastore
from google.cloud import vision
from PIL import Image

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


def get_label_annotations(v_client, image):
    # TODO: Improve docstring
    """Retrieve image's label annotations from Cloud Vision API.

    Arg: google.cloud.vision_v1.types.Image

    Returns:
        labels (list): List of EntityAnnotation objects. E.g., [mid: "/m/02mhj"
        description: "ecosystem" score: 0.9368894100189209 topicality: 0.9368894100189209, ...]
        See https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#EntityAnnotation
    """
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
    # To convert normalized_verticies to verticies, multiply the x field of the
    # normalized_vertex by the width of the picture to get the x field of the
    # vertex, and multiply the y field of the normalized_vertex by the height of
    # the image to get the y of the vertex.
    pim = Image.open(filepath)
    width, height = pim.size
    object_annotations = list()
    for o in response.localized_object_annotations:
        oa = dict()
        vects = o.bounding_poly.normalized_vertices
        oa["name"] = o.name
        oa["crop_box"] = [vects[0].x * width, vects[0].y * height,
                          vects[2].x * width - 1, vects[2].y * height - 1]
        object_annotations.append(oa)
    logger.debug(f"Returning object annotations: {object_annotations}")
    return object_annotations


def get_crop_hints(v_client, filepath):
    # TODO: Docstring
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
    # TODO: Docstring
    """
    s_a dict
    If it is likely or very likey that image contains adult, medical, spoofed,
    violent, or racy content, return False.
    """
    return all(x not in safety_annotations.values() for x in ["LIKELY", "VERY_LIKELY"])


def is_bird(labels):
    # TODO Docstring
    """l_a list"""
    return any(x in labels for x in ["bird", "seabird", "beak"])


def classify_entity(v_client, entity):
    # TODO: Docstring
    """
    """
    name = entity.key.name
    filepath = download_image(url=entity.get("download_url"),
                              name=name)
    # Find objects in image.
    logger.debug(f"Requesting object detection for {entity.key.name}...")
    try:
        obs = get_object_annotations(v_client, filepath)
        return
        ### UP TO DATE ^^^ NEED TO FIX vvv ###

        object_names = list(o.name.lower() for o in obs)
        entity.update({
            "object_labels": json.dumps(object_names),
            "is_bird": is_bird(object_names)
        })
        logger.debug(f"First pass: {entity.key.name} is_bird = {entity.get('is_bird')}")
    except exceptions.GoogleAPIError as e:
        logger.exception(e)

    # Double check non-bird.
    if not entity.get("is_bird") == True:
        # Crop and annotate.
        try:
            crop_path = crop_to_hints(v_client, filepath)
        except exceptions.GoogleAPIError:
            crop_path = None
        try:
            if crop_path:
                label_annotations = get_label_annotations(v_client, vision_img_from_path(v_client, crop_path))
            else:
                label_annotations = get_label_annotations(v_client, img)
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
        neg_path = os.path.join(os.path.dirname(__file__), f'assets/negative/{entity.key.name}.jpg')
        logger.debug(f"Moving from {filepath} to {neg_path}")
        os.rename(filepath, neg_path)

    if entity.get("is_bird") != None:
        entity.update({"is_classified": True})
    logger.debug(entity)
    return


def crop_to_hints(v_client, filepath):
    # TODO: Docstring
    # https://cloud.google.com/vision/docs/crop-hints 
    vects = get_crop_hints(v_client, vision_img_from_path(v_client, filepath))
    im = Image.open(filepath)
    im2 = im.crop([vects[0].x, vects[0].y,
                   vects[2].x - 1, vects[2].y - 1])
    if not os.path.exists("assets/cropped"):
        pathlib.Path("assets/cropped").mkdir(parents=True)
    # Recover entity.key.name -- e.g., `Flickr-1234` -- from filepath.
    name = filepath.split("/")[-1][:-4]
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

        entities = pull_unclassified_entities(ds_client)
        entity = random.choice(entities)
        filepath = download_image(url=entity.get("download_url"),
                                  name=entity.key.name)
        obs = get_object_annotations(v_client, filepath)
        im = Image.open(filepath)
        im2 = im.crop(obs[0]["crop_box"])
        if not os.path.exists("assets/cropped"):
            pathlib.Path("assets/cropped").mkdir(parents=True)
        crop_path = os.path.join(os.path.dirname(__file__), f'assets/cropped/{entity.key.name}_cropped.jpg')
        im2.save(crop_path, 'JPEG')
        im.show()
        im2.show()

        # classify_unclassified_entities(ds_client, v_client)
        logger.info(f"Finished {filename}.")
    except Exception as e:
        logger.exception(e)
