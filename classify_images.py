#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import io
import json
import logging
import os
import pathlib
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
    """Retrieves entities from datastore that lack a value for vision_labels.

    Returns:
        entities (list): List of Photo entities from Cloud Datastore project
        beachbirbys. E.g., [<Entity('Photo', 'Flickr-36092472285') {'source':
        'Flickr', ...}, ...]
    """
    query = ds_client.query(kind="Photo")
    query.add_filter("vision_labels", "=", None)
    entities = list(query.fetch())
    logger.info(f"Retrieved {len(entities)} unclassified entities.")
    logger.debug(entities)
    return entities


def download_image(url, filename):
    """Downloads image from url, saves as filename, returns filepath."""
    if not os.path.exists('assets'):
        pathlib.Path('assets').mkdir(parents=True, exist_ok=True)
    logger.debug(f"Opening {url}...")
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        filepath = os.path.join(os.path.dirname(__file__), f'assets/{filename}.jpg')
        with open(filepath, 'wb') as image:
            for chunk in r:
                image.write(chunk)
        logger.debug(f"Saved image as {filepath}")
    else:
        logger.error(f"Failed to download {filename} from {url}")
        raise Exception(f"Failed to download {filename} from {url}")
    return filepath


def image_labels_from_file(v_client, filepath):
    """Retrieve image's label annotations from Cloud Vision API.

    Returns:
        labels (list): List of EntityAnnotation objects. E.g., [mid: "/m/02mhj"
        description: "ecosystem" score: 0.9368894100189209 topicality: 0.9368894100189209, ...]
        See https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#EntityAnnotation
    """
    logger.debug(f"Opening {filepath}...")
    with io.open(filepath, 'rb') as image_file:
        content = image_file.read()
    image = vision.types.Image(content=content)

    logger.debug(f"Requesting label detection for {filepath}...")
    response = v_client.label_detection(image=image)
    logger.debug(response)
    labels = response.label_annotations
    return labels


def classify_entities(v_client, entities):
    for entity in entities:
        filepath = download_image(url=entity.get("download_url"),
                                  filename=entity.key.name)
        raw_labels = image_labels_from_file(v_client, filepath)
        if not raw_labels:
            logger.error(f"No labels for {entity.key.name}: {raw_labels}")
            raise Exception(f"No labels for {entity.key.name}.")
        entity.update({
            "vision_labels": json.dumps(list(l.description for l in raw_labels)),
            "is_bird": is_bird(set(l.description for l in raw_labels)),
            "entity_updated": datetime.datetime.utcnow()
        })
    logger.info(f"Classified {len(entities)} entities.")
    logger.debug(entities)
    return


def is_bird(descriptions):
    if "bird" in descriptions:
        return True
    return False

################################################################################
if __name__ == "__main__":
    filename = os.path.basename(__file__)
    logger.info(f"Starting {filename}...")
    try:
        ds_client = datastore.Client()
        v_client = vision.ImageAnnotatorClient()
        entities = pull_unclassified_entities(ds_client)
        if entities:
            classify_entities(v_client, entities)
            write_entities_to_datastore(ds_client, entities)
        logger.info(f"Finished {filename}.")
    except Exception as e:
        logger.exception(e)
