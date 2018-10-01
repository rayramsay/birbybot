#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: Update initial entitity values in flickr_to_datastore.py

import datetime
import io
import json
import logging
import os
import pathlib
import random
import sys

import requests
from google.cloud import datastore
from google.cloud import vision

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


def download_image(url, filename):
    # TODO: Improve docstring
    """Downloads image from url, saves as filename, returns filepath.
    
    Returns:
        str 
    """
    if not os.path.exists("assets"):
        pathlib.Path("assets").mkdir(parents=True)
    filepath = os.path.join(os.path.dirname(__file__), f'assets/{filename}.jpg')
    
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
        logger.error(f"Failed to download {filename} from {url}")
        r.raise_for_status()
    return filepath


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


def create_safety_annotations(v_client, image):
    # TODO: Docstring
    """ arg google.cloud.vision_v1.types.Image"""
    # https://cloud.google.com/vision/docs/detecting-safe-search
    response = v_client.safe_search_detection(image=image)
    logger.debug(f"API response for safe_search_detection: {response}")
    if not response.safe_search_annotation:
        logger.error(f"No safety annotations for image.")
        raise Exception(f"No safety annotations for image. Vision API response: {response}")
    likelihood_name = ('UNKNOWN', 'VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE',
                       'LIKELY', 'VERY_LIKELY')
    safety_annotations = {"adult": likelihood_name[response.safe_search_annotation.adult],
                          "medical": likelihood_name[response.safe_search_annotation.medical],
                          "spoofed": likelihood_name[response.safe_search_annotation.spoof],
                          "violence": likelihood_name[response.safe_search_annotation.violence],
                          "racy": likelihood_name[response.safe_search_annotation.racy]}
    logger.debug(f"Returning safety_annotations: {safety_annotations}")
    return safety_annotations


def create_label_annotations(v_client, image):
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
        raise Exception(f"No label annotations for image. Vision API response: {response}")
    labels = list(l.description for l in response.label_annotations)
    logger.debug(f"Returning label annotations: {labels}")
    return labels


def is_safe(safety_annotations):
    # TODO: Docstring
    """
    s_a dict
    If it is likely or very likey that image contains adult, medical, spoofed,
    violent, or racy content, return False.
    """
    return all(x not in safety_annotations.values() for x in ["LIKELY", "VERY_LIKELY"])


def is_bird(label_annotations):
    # TODO Docstring
    """l_a list"""
    return "bird" in label_annotations


def classify_entity(v_client, entity):
    # TODO: Docstring
    """
    """
    # Save image from URL.
    filepath = download_image(url=entity.get("download_url"),
                              filename=entity.key.name)
    # Open image as google.cloud.vision_v1.types.Image.
    img = vision_img_from_path(v_client, filepath)
    
    # Check that image is safe to tweet.
    logger.debug(f"Requesting safe search detection for {entity.key.name}...")
    safety_annotations = create_safety_annotations(v_client, img)
    entity.update({
        "safety_labels": json.dumps(safety_annotations),
        "is_safe": is_safe(safety_annotations)
    })
    
    # Classify image as bird.
    logger.debug(f"Requesting label detection for {entity.key.name}...")
    label_annotations = create_label_annotations(v_client, img)
    entity.update({
        "vision_labels": json.dumps(label_annotations),
        "is_bird": is_bird(label_annotations)
    })

    entity.update({"is_classified": True})
    logger.debug(entity)
    return


def 

################################################################################
if __name__ == "__main__":
    filename = os.path.basename(__file__)
    logger.info(f"Starting {filename}...")
    try:
        ds_client = datastore.Client()
        v_client = vision.ImageAnnotatorClient()
        entities = pull_unclassified_entities(ds_client)
        if entities:
            non_safe = 0
            non_birds = 0
            for entity in entities:
                logger.debug(f"Classifying {entity.key.name}...")
                classify_entity(v_client, entity)
                logger.debug(f"Saving {entity.key.name} in datastore...")
                ds_client.put(entity)
                if entity.get("is_safe") == False:
                    non_safe += 1
                if entity.get("is_bird") == False:
                    non_birds += 1
            logger.info(f"Classified and updated {len(entities)} entities.")
            logger.info(f"{non_safe} entities were classified as not safe.")
            logger.info(f"{non_birds} entities were classified as not birds.")
        logger.info(f"Finished {filename}.")
    except Exception as e:
        logger.exception(e)
