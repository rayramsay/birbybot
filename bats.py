#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import io
import json
import logging
import os
import pathlib
import random
import sys

import requests
from flickrapi import FlickrAPI
from google.api_core import exceptions
from google.cloud import datastore, vision
from PIL import Image

import utils

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
utils.configure_logger(logger, console_output=True)
### HELPERS ####################################################################
def pick_download_url(entity):
    """Returns large image size (1024 on longest side) url if available. Falls
    back to medium 800 size, medium 640 size, and finally original size.
    
    Args:
        entity (google.cloud.datastore.entity.Entity): Flickr Photo entity
    
    Returns:
        str: URL of prefered photo size.
    """
    # How Flickr urls relate to Flickr photo sizes:
    # https://www.flickr.com/services/api/misc.urls.html
    # https://www.flickr.com/groups/51035612836@N01/discuss/72157629805170802/72157629809933878
    # Cloud Vision API recommended image sizes:
    # https://cloud.google.com/vision/docs/supported-files
    # Twitter media file size limits and display dimensions:
    # https://developer.twitter.com/en/docs/media/upload-media/uploading-media/media-best-practices.html
    # https://sproutsocial.com/insights/social-media-image-sizes-guide/#twitter

    # Prefer url_l to url_c to url_z to url_o.
    if entity.get("url_l"):
        url = entity["url_l"]
    elif entity.get("url_c"):
        url = entity["url_c"]
    elif entity.get("url_z"):
        url = entity["url_z"]
    else:
        url = entity["url_o"]
    return url


def download_image(url, name):
    """Downloads image from url, saves in assets folder as name.jpg, returns
    filepath.
    
    Returns:
        str
    """
    assets_path = os.path.join(os.path.dirname(__file__), "assets")
    if not os.path.exists(assets_path):
        pathlib.Path(assets_path).mkdir(parents=True)
    filepath = os.path.join(assets_path + f"/{name}.jpg")
    
    # If we've already downloaded the image, just return.
    if os.path.exists(filepath):
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

# Create Flickr API client.
FLICKR_PUBLIC = os.environ['FLICKR_KEY']
FLICKR_SECRET = os.environ['FLICKR_SECRET']
flickr = FlickrAPI(FLICKR_PUBLIC, FLICKR_SECRET, format="parsed-json")

# Create Cloud Datastore and Vision clients.
ds_client = datastore.Client()
v_client = vision.ImageAnnotatorClient()

# Search Flickr for bats!
search_terms = "bat"
params = {"text": search_terms,
          "license": "1,2,3,4,5,6,8,9,10",
          "media": "photos",
          "safe_search": "1",
          "extras": "license,date_upload,owner_name,url_z,url_c,url_l,url_o",
          "sort": "relevance",
          "per_page": "10"}
try:
    resp = flickr.photos.search(**params)
    photos = resp["photos"]["photo"]
except (requests.exceptions.ConnectionError, KeyError) as e:
    logger.exception(e)
    sys.exit()

# Turn Flickr results into entities.
entities = list()
for photo in photos:
    kind = "Photo"
    name = "Flickr-" + photo.get("id")
    key = ds_client.key(kind, name)
    entity = datastore.Entity(key=key)
    entity.update({
        "source": "Flickr",
        "search_terms": search_terms,
        "is_classified": False
    })
    for k, v in photo.items():
        if not k == "dateupload":
            entity.update({k: v})
        else:
            entity.update({k: datetime.datetime.utcfromtimestamp(int(v))})
    entity.update({"download_url": pick_download_url(entity)})
    logger.debug(entity)

    # Rather than upserting the entity now and later retrieving the unclassified
    # entities from Cloud Datastore, let's boldly continue into classification.

    # Download image. (You can use Cloud Vision API with a remote image, but
    # it's flaky.)
    name = entity.key.name
    try:
        filepath = download_image(url=entity.get("download_url"),
                                  name=name)
    except requests.exceptions.HTTPError as e:
        logger.exception(e)
        continue
    
    # Load image.
    logger.debug(f"Opening {name}...")
    with io.open(filepath, 'rb') as image_file:
        content = image_file.read()
    image = vision.types.Image(content=content)

    # Label image as a whole and find objects in image.
    logger.info(f"Starting classification for for {name}...")
    try:
        response = v_client.annotate_image({
            "image": image,
            "features": [{'type': vision.enums.Feature.Type.OBJECT_LOCALIZATION},
                        {'type': vision.enums.Feature.Type.LABEL_DETECTION}]
        })
        logger.debug(f"Response for {name} annotation request: {response}")
    except exceptions.GoogleAPIError as e:
        logger.exception(e)
        continue
    
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

    # Are you a bat?
    def is_a(col, labels):
        return any(x in labels for x in col)
   
    # If it's not a bat but there are crop boxes, let's crop and get new labels.
    if not is_a(["bat"], labels) and crop_boxes:
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
                response = v_client.label_detection(image=img)
                logger.debug(f"Response for crop label detection request: {response}")
            except exceptions.GoogleAPIError as e:
                logger.exception(e)
                continue
            if response.label_annotations:
                labels.update([a.description for a in response.label_annotations])
                if is_a(["bat"], labels):
                    # We found a bat, let's stop cropping and labeling.
                    break
        im.close()
        logger.debug("Done cropping {name}.")
    
    logger.debug(f"{name}'s labels: {labels}")
    entity.update({
        "is_bat": is_a(["bat"], labels),
        "vision_labels": json.dumps(list(labels)),
        "is_classified": True
    })
    logger.info(f"{name} is_bat = {entity.get('is_bat')}!\n\n")
    entities.append(entity)
    
    # We've done what we can -- upsert that entitity! (We could also batch
    # these, or use a transaction if we needed to perform get and update
    # operations in a single atomical transaction.)
    try:
        ds_client.put(entity)
    except exceptions.GoogleAPIError as e:
        logger.exception(e)
        continue

# Get bats from Cloud Datastore.
logger.info(f"Retrieving is_bat entities...")
query = ds_client.query(kind="Photo")
query.add_filter("is_bat", "=", True)
# If you don't want to load a potentially huge number of entities into memory,
# you can make the query keys_only and then get a single entitity by key.
try:
    entities = list(query.fetch())
    logger.debug(entities)
except exceptions.GoogleAPIError as e:
    logger.exception(e)

# We made a list of entities up above, so even if retrieving them from Cloud
# Datastore failed, they're still in memory.
entity = random.choice(entities)

# I can't believe it's finally time to tweet.
