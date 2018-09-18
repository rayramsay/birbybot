#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import os
import random
import sys

import requests
from flickrapi import shorturl
from twython import Twython

import utils

### LOGGING ####################################################################
logger = logging.getLogger(__name__)
utils.configure_logger(logger, console_output=True)
### GLOBALS ####################################################################
try:
    CONSUMER_KEY = os.environ['TWITTER_CONSUMER_KEY']
    CONSUMER_SECRET = os.environ['TWITTER_CONSUMER_SECRET']
    ACCESS_TOKEN = os.environ['TWITTER_ACCESS_TOKEN']
    ACCESS_TOKEN_SECRET = os.environ['TWITTER_ACCESS_SECRET']
except KeyError as e:
    logger.exception(e)
    sys.exit(1)
################################################################################


def get_random_photo(json_file):
    """Opens .json file and returns a photo dict."""
    with open(json_file, 'r') as f:
        photos = json.load(f)
    photo = random.choice(photos)
    return photo


def download_image(url):
    # Prefer url_l > url_c > url_z > url_o
    """Downloads image from URL."""
    filename = 'temp.jpg'
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(filename, 'wb') as image:
            for chunk in r:
                image.write(chunk)
    else:
        raise Exception("Failed to download " + url)


def create_message(photo):
    """Takes photo dict and returns message string."""
    title = photo['title']
    photographer = photo['ownername']
    shortlink = shorturl.url(photo['id'])
    message = f'{title} by {photographer} {shortlink} #birbybot'
    return message


def tweet_photo(message, photo_filename):
    twitter = Twython(
        CONSUMER_KEY,
        CONSUMER_SECRET,
        ACCESS_TOKEN,
        ACCESS_TOKEN_SECRET
    )
    img = open(photo_filename, 'rb')
    try:
        response = twitter.upload_media(media=img)
        twitter.update_status(status=message, media_ids=[response['media_id']])
        log(message)
        os.remove(photo_filename)
    except Exception as error:
        log(str(error))
        raise

if __name__ == "__main__":
    photo = get_random_photo("plover_1530909825.json")
    download_image(photo['url_o'])
    message = create_message(photo)
    tweet_photo(message, "temp.jpg")
