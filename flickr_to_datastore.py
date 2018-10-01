#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import os

from dateutil.relativedelta import relativedelta
from flickrapi import FlickrAPI
from google.cloud import datastore

import utils

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
utils.configure_logger(logger, console_output=True)
################################################################################

def create_entities_from_search(ds_client, search_terms, min_upload_date=None):
    """Searches Flickr for non-copyrighted photos matching `search_terms`
    (optionally, uploaded since `min_upload_date`), and then creates Cloud
    Datastore Photo entities from search results.

    Args:
        ds_client (google.cloud.datastore.client.Client)

        search_terms (str): A free text search. Photos whose title, description
        or tags contain the text will be returned. You can exclude results that
        match a term by prepending it with a - character.

        min_upload_date (str, optional): Photos with an upload date greater than
        or equal to this value will be returned. The date can be in the form of
        a Unix timestamp or MySQL datetime. Defaults to None.

    Returns:
        list of google.cloud.datastore.entity.Entity of kind 'Photo': Entity
        keys are patterned after 'Flickr-{photo.id}'. Example: [<Entity('Photo',
        'Flickr-36092472285') {'source': 'Flickr', 'license': '4', ...}>, ...]
    """
    # Explanation of Flickr search parameters:
    # https://www.flickr.com/services/api/flickr.photos.search.html
    # https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html
    # https://www.flickr.com/services/api/misc.urls.html
    
    # Walking Flickr search results and creating Datastore entities:
    # https://github.com/sybrenstuvel/flickrapi/blob/master/doc/7-util.rst#walking-through-a-search-result
    # https://github.com/GoogleCloudPlatform/python-docs-samples/tree/master/datastore/cloud-client

    try:
        FLICKR_PUBLIC = os.environ['FLICKR_KEY']
        FLICKR_SECRET = os.environ['FLICKR_SECRET']
    except KeyError as e:
        logger.exception(e)
        raise

    logger.debug(f"Searching for photos of '{search_terms}' uploaded since {min_upload_date}...")
    flickr = FlickrAPI(FLICKR_PUBLIC, FLICKR_SECRET, format="etree")  # Walk requires ElementTree
    params = {"text": search_terms,
              "license": "1,2,3,4,5,6,8,9,10",  # All licenses except All Rights Reserved & 'No known copyright restrictions' (latter excluded due to poor quality results)
              "media": "photos",
              "safe_search": "1",
              "extras": "license,date_upload,owner_name,url_z,url_c,url_l,url_o",
              "min_upload_date": min_upload_date}
    entities = list()
    exclude_from_indexes = ["secret",
                            "server",
                            "farm",
                            "ispublic",
                            "isfriend",
                            "isfamily",
                            "url_z",
                            "url_c",
                            "url_l",
                            "url_o",
                            "height_z",
                            "height_c",
                            "height_l",
                            "height_o",
                            "width_z",
                            "width_c",
                            "width_l",
                            "width_o"]
    for photo in flickr.walk(**params):  # Creates a generator
        kind = "Photo"
        name = "Flickr-" + photo.get("id")
        key = ds_client.key(kind, name)
        entity = datastore.Entity(key=key, exclude_from_indexes=exclude_from_indexes)
        entity.update({
            "source": "Flickr",
            "search_terms": search_terms,
            "last_tweeted": datetime.datetime.utcfromtimestamp(1514764800),  # 1/1/18
            "vision_labels": None,
            "is_bird": None
        })
        for k, v in photo.items():
            if not k == "dateupload":
                entity.update({k: v})
            else:
                entity.update({k: datetime.datetime.utcfromtimestamp(int(v))})
        entity.update({"download_url": get_download_url(entity)})
        entities.append(entity)
    logger.info(f"Found {len(entities)} photos of '{search_terms}' uploaded since {min_upload_date}.")
    logger.debug(entities)
    return entities


def get_download_url(entity):
    """Returns large image size (1024 on longest side) url if available. Falls
    back to medium 800 size, medium 640 size, and finally original size.
    
    Args:
        entity (google.cloud.datastore.entity.Entity): Flickr Photo entity
        instantiated by `create_entities_from_search()`.
    
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


def write_entities_to_datastore(ds_client, entities):
    logger.debug(f"Writing {len(entities)} entities to Cloud Datastore for project beachbirbys...")
    with ds_client.batch():
        ds_client.put_multi(entities)
    logger.info(f"Wrote {len(entities)} entities to Cloud Datastore for project beachbirbys.")
    return

################################################################################
if __name__ == "__main__":
    filename = os.path.basename(__file__)
    logger.info(f"Starting {filename}...")
    try:
        # This script is designed to be run on the first of the month in order
        # to find photos uploaded to Flickr during the previous month.
        ds_client = datastore.Client()
        search_terms = ["plover chick", "plover hatchling", "plover baby",
                        "sandpiper chick", "sandpiper hatchling", "sandpiper baby"]
        first_day_of_previous_month = (datetime.datetime.utcnow().replace(day=1) - relativedelta(months=1)).strftime("%Y-%m-%d")
        for term in search_terms:
            entities = create_entities_from_search(ds_client, term, min_upload_date=first_day_of_previous_month)
            if entities:
                write_entities_to_datastore(ds_client, entities)
        logger.info(f"Finished {filename}.")
    except Exception as e:
        logger.exception(e)
