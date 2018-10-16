#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import io
import json
import logging
import os
import pathlib
import pprint
import random
import sys

import requests
from dateutil import parser
from flickrapi import FlickrAPI, shorturl
from google.api_core import exceptions
from google.cloud import datastore, vision
from PIL import Image
from twython import Twython

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
### HELPERS ####################################################################
def pick_download_url(entity):
    """Prefer url_l to url_c to url_z to url_o."""
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
    filepath."""
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
 
def is_a(lst, labels):
    return any(x in labels for x in lst)

def show_photos(entities):
    """What the heck did we get back from Flickr?"""
    for entity in entities:
        name = entity.key.name
        try:
            filepath = download_image(url=entity.get("download_url"),
                                      name=name)
            with Image.open(filepath) as im:
                im.show()
        except requests.exceptions.HTTPError as e:
            logger.exception(e)
            continue

def classify_as_resp_only(terms, entities):
    for entity in entities:
        logger.debug(entity)
        name = entity.key.name
        try:
            filepath = download_image(url=entity.get("download_url"),
                                      name=name)
        except requests.exceptions.HTTPError as e:
            logger.exception(e)
            continue
        logger.debug(f"Opening {name}...")
        try:
            with io.open(filepath, 'rb') as image_file:
                content = image_file.read()
            image = vision.types.Image(content=content)
        except Exception as e:
            logger.exception(e)
            continue
        logger.info(f"Starting classification for {name}...")
        try:
            response = v_client.annotate_image({
                "image": image,
                "features": [{'type': vision.enums.Feature.Type.LABEL_DETECTION},
                             {'type': vision.enums.Feature.Type.OBJECT_LOCALIZATION}]
            })
            logger.debug(f"Response for {name} annotation request: {response}")
        except exceptions.GoogleAPIError as e:
            logger.exception(e)
            continue

################################################################################

# Instantiate clients.
flickr = FlickrAPI(
    os.environ['FLICKR_KEY'],
    os.environ['FLICKR_SECRET'],
    format="parsed-json"
)
twitter = Twython(
    os.environ['TWITTER_CONSUMER_KEY'],
    os.environ['TWITTER_CONSUMER_SECRET'],
    os.environ['TWITTER_ACCESS_TOKEN'],
    os.environ['TWITTER_ACCESS_SECRET']
)
ds_client = datastore.Client()
v_client = vision.ImageAnnotatorClient()

# Search Flickr for bats!
def search_flickr(search_string):
    params = {"text": search_string,
              "license": "1,2,3,4,5,6,8,9,10",
              "media": "photos",
              "safe_search": "1",
              "extras": "license,date_upload,owner_name,url_z,url_c,url_l,url_o",
              "min_upload_date": "2018-01-01",  # Surface interesting cases
              "sort": "date-posted-asc",
              "per_page": "5"}
    resp = flickr.photos.search(**params)
    photos = resp["photos"]["photo"]
    return photos

# Turn Flickr results into entities.
def photos_to_entities(photos):
    entities = list()
    for photo in photos:
        kind = "Photo"
        name = "Flickr-" + photo.get("id")
        key = ds_client.key(kind, name)
        entity = datastore.Entity(key=key)
        entity.update({
            "source": "Flickr",
            "search_terms": "bat",
            "is_classified": False
        })
        for k, v in photo.items():
            if not k == "dateupload":
                entity.update({k: v})
            else:
                entity.update({k: datetime.datetime.utcfromtimestamp(int(v))})
        entity.update({"download_url": pick_download_url(entity)})
        entities.append(entity)
    return entities

# Classify photos!
def classify_as(terms, entities):
    for entity in entities:
        logger.debug(entity)
        name = entity.key.name

        # Download image. (You can use Cloud Vision API with a remote image, but
        # it's flaky.)
        try:
            filepath = download_image(url=entity.get("download_url"),
                                      name=name)
        except requests.exceptions.HTTPError as e:
            logger.exception(e)
            continue
        
        # Load image.
        logger.debug(f"Opening {name}...")
        try:
            with io.open(filepath, 'rb') as image_file:
                content = image_file.read()
            image = vision.types.Image(content=content)
        except Exception as e:
            logger.exception(e)
            continue
        
        # Label image as a whole and find objects in image.
        logger.info(f"Starting classification for {name}...")
        try:
            response = v_client.annotate_image({
                "image": image,
                "features": [{'type': vision.enums.Feature.Type.LABEL_DETECTION},
                             {'type': vision.enums.Feature.Type.OBJECT_LOCALIZATION}]
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

        # If it's not a bat but there are crop boxes, let's crop and get new labels.
        if not is_a(terms, labels) and crop_boxes:
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
                    if is_a(terms, labels):
                        # We found a bat, let's stop cropping and labeling.
                        break
            im.close()
            logger.debug(f"Done cropping {name}.")
        
        logger.debug(f"{name}'s labels: {labels}")
        entity.update({
            "is_bat": is_a(terms, labels),
            "vision_labels": json.dumps(list(labels)),
            "is_classified": True
        })
        logger.info(f"{name} is_bat = {entity.get('is_bat')}!\n")
    logger.debug(f"Processed {len(entities)} entities.")
    return

def tweet_photo_entity(entity):
    name = entity.key.name
    logger.info(f"Tweeting {name}...")
    logger.debug(entity)

    # Write a message.
    title = entity.get("title")
    photographer = entity.get("ownername")
    shortlink = shorturl.url(entity.get("id"))
    message = f"{title} by {photographer} {shortlink} #HappyHalloween"
    logger.debug(message)

    # Download image if we somehow don't already have it.
    filepath = os.path.join(os.path.dirname(__file__), f'assets/{name}.jpg')
    if not pathlib.Path(filepath).exists():
        filepath = download_image(url=entity.get("download_url"),
                                  name=name)

    # Load image and tweet.
    try:
        with io.open(filepath, 'rb') as img:
            upload_resp = twitter.upload_media(media=img)
            logger.debug(upload_resp)
        tweet_resp = twitter.update_status(status=message,
                                           media_ids=[upload_resp["media_id"]])
        logger.debug(tweet_resp)
    except Exception as e:
        logger.exception(e)
        sys.exit()

    # Finally, let's remember when we tweeted. We could add a composite index so
    # that we'd only pull bat photos that we hadn't tweeted recently.
    try:
        entity.update({
            "last_tweeted": parser.parse(tweet_resp.get("created_at"))
        })
        ds_client.put(entity)
    except Exception as e:
        logger.exception(e)

################################################################################
if __name__ == "__main__":
    pp = pprint.PrettyPrinter()

    photos = search_flickr("bat")
    pp.pprint(photos)

    # entities = photos_to_entities(photos)
    # pp.pprint(entities)

    # At this point, we could write the entities to Cloud Datastore, and then
    # retrieve entities where is_classified is False. But let's just boldly
    # continue!

    # show_photos(entities)  # TODO Comment out

    # Before we discuss classify_as, let's look at the Vision API response.
    # classify_as_resp_only(["bat"], [entities[-1]])  # TODO Comment out

    # classify_as(["bat"], entities)
    # pp.pprint(entities)

    # Now that our entities are classified, let's add them to Cloud Datastore.
    # We could also batch these, or use a transaction if we needed to perform
    # get and update operations in a single atomical transaction.
    # for entity in entities:
    #     ds_client.put(entity)

    # Get bats from Cloud Datastore.
    # query = ds_client.query(kind="Photo")
    # query.add_filter("is_bat", "=", True)
    # If you don't want to load a potentially huge number of entities into memory,
    # you can make the query keys_only and then get a single entitity by key.
    # bats = list(query.fetch())
    # pp.pprint(bats)

    # Time to tweet!
    # tweet_photo_entity(random.choice(bats))
