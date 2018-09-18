#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import os
import sys

from flickrapi import FlickrAPI
from google.cloud import datastore

import utils

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
utils.configure_logger(logger, console_output=True)
### GLOBALS ####################################################################
try:
    FLICKR_PUBLIC = os.environ['FLICKR_KEY']
    FLICKR_SECRET = os.environ['FLICKR_SECRET']
except KeyError as e:
    logger.exception(e)
    sys.exit(1)
################################################################################

def create_entities_from_search(search_terms, min_upload_date=None):
    """Searches Flickr for non-copyrighted photos matching `search_terms` and
    creates Cloud Datastore entities from search results.

    Args:
        search_terms (str): A free text search. Photos whose title, description
        or tags contain the text will be returned. You can exclude results that
        match a term by prepending it with a - character.

        min_upload_date (str): MySQL datetime or Unix timestamp.

    Returns:
        entities (list): List of Photo entities for Cloud Datastore project
        beachbirbys. Entity keys take the form of 'Flickr-{photo.id}': e.g.,
        [<Entity('Photo', 'Flickr-36092472285') {'source': 'Flickr', ...}, ...]
    """
    # Explanation of Flickr search parameters:
    # https://www.flickr.com/services/api/flickr.photos.search.html
    # https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html
    # https://www.flickr.com/services/api/misc.urls.html
    
    # Walking Flickr search results and creating Datastore entities:
    # https://github.com/sybrenstuvel/flickrapi/blob/master/doc/7-util.rst#walking-through-a-search-result
    # https://github.com/GoogleCloudPlatform/python-docs-samples/tree/master/datastore/cloud-client

    flickr = FlickrAPI(FLICKR_PUBLIC, FLICKR_SECRET, format="etree")  # Walk requires ElementTree
    params = {"text": search_terms,
              "license": "1,2,3,4,5,6,7,8,9,10",  # All licenses except All Rights Reserved
              "sort": "relevance",
              "media": "photos",
              "extras": "license,date_upload,owner_name,url_z,url_c,url_l,url_o",
              "min_upload_date": min_upload_date}

    ds_client = datastore.Client(project="beachbirbys")
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
            "search_terms": search_terms
        })
        for k, v in photo.items():
            if not k == "dateupload":
                entity.update({k: v})
            else:
                entity.update({k: datetime.datetime.utcfromtimestamp(int(v))})
        entities.append(entity)
    logger.debug(entities)
    return entities

def write_entities_to_datastore(entities, project_id):
    # TODO
    return

################################################################################
if __name__ == "__main__":
    filename = os.path.basename(__file__)
    logger.debug("Starting {filename}...".format(filename=filename))
    try:
        entities = create_entities_from_search("plover baby", "2017-01-01")
        if entities:
            write_entities_to_datastore(entities, "beachbirbys")
        logger.debug("Finished {filename}.".format(filename=filename))
    except Exception as e:
        logger.exception(e)
