#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import json
import logging
import os
import pathlib

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


def move_neg(original_path):
    """Given JPG location, moves to path/to/assets/negative/name.jpg."""
    name = utils.name_from_path(original_path)
    if not os.path.exists("assets/negative"):
        pathlib.Path("assets/negative").mkdir(parents=True)
    neg_path = os.path.join(os.path.dirname(__file__), f'assets/negative/{name}.jpg')
    logger.debug(f"Moving from {original_path} to {neg_path}")
    os.rename(original_path, neg_path)
    return neg_path


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
    name = entity.key.name
    # Download from URL.
    filepath = utils.download_image(url=entity.get("download_url"),
                                    name=name)
    # Instantiate google.cloud.vision_v1.types.Image.
    image = utils.vision_img_from_path(v_client, filepath)

    # Label image as a whole and find objects in image.
    logger.info(f"Starting classification for {name}...")
    response = v_client.annotate_image({
        "image": image,
        "features": [{'type': vision.enums.Feature.Type.LABEL_DETECTION},
                     {'type': vision.enums.Feature.Type.OBJECT_LOCALIZATION}]
    })
    logger.debug(f"Response for {name} annotation request: {response}")

    labels = set()
    crop_boxes = set()
    if response.label_annotations:
        labels.update([a.description for a in response.label_annotations])
    if response.localized_object_annotations:
        labels.update([a.name.lower() for a in response.localized_object_annotations])
        # While we're here, let's save crop boxes.
        with Image.open(filepath) as im:
            width, height = im.size
        for a in response.localized_object_annotations:
            verts = a.bounding_poly.normalized_vertices
            crop_boxes.add(( round(verts[0].x * width),
                             round(verts[0].y * height),
                             round(verts[2].x * width),
                             round(verts[2].y * height) ))
    # If it's not a bird but there are crop boxes, let's crop and get new labels.
    if not is_bird(labels) and crop_boxes:
        logger.debug(f"Cropping {name}...")
        im = Image.open(filepath)
        for cb in crop_boxes:
            with im.crop(box=cb) as im2:
                # Convert PIL.Image.Image to bytes.
                with io.BytesIO() as buffer:
                    im2.save(buffer, format='JPEG')
                    byts = buffer.getvalue()
                    img = vision.types.Image(content=byts)
            logger.debug(f"Requesting label detection for crop...")
            try:
                r = v_client.label_detection(image=img)
                logger.debug(f"Response for crop label detection request: {r}")
            except exceptions.GoogleAPIError as e:
                logger.exception(e)
                continue
            if r and r.label_annotations:
                labels.update([a.description for a in r.label_annotations])
                if is_bird(labels):
                    # We found a bird, let's stop cropping and labeling.
                    break
        im.close()
        logger.debug(f"Done cropping {name}.")
    
    logger.debug(f"{name}'s labels: {labels}")
    entity.update({
        "is_bird": is_bird(labels),
        "vision_labels": utils.trim(json.dumps(list(labels))),
        "is_classified": True
    })
    logger.debug(entity)
    
    # Move non-birds to different folder so that they are easier to manually review.
    if entity.get("is_bird") == False:
        move_neg(filepath)
    return


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
