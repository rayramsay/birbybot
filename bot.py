#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import random
from time import gmtime, strftime

import requests
from twython import Twython
from flickrapi import shorturl

############# GLOBALS ##############
# Remember to ``source secrets.sh``!
CONSUMER_KEY = os.environ['TWITTER_CONSUMER_KEY']
CONSUMER_SECRET = os.environ['TWITTER_CONSUMER_SECRET']
ACCESS_TOKEN = os.environ['TWITTER_ACCESS_TOKEN']
ACCESS_TOKEN_SECRET = os.environ['TWITTER_ACCESS_SECRET']
####################################


# https://github.com/molly/twitterbot_framework/blob/master/bot.py#L57-L62
def log(string):
    path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    with open(os.path.join(path, "birbybot.log"), 'a+') as f:
        t = strftime("%d %b %Y %H:%M:%S", gmtime())
        f.write("\n" + t + " " + string)


def get_random_photo(json_file):
    """Opens .json file and returns a photo dict."""
    with open(json_file, 'r') as f:
        photos = json.load(f)
    photo = random.choice(photos)
    return photo


def download_image(url):
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
