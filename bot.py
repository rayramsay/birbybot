#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import random
from time import gmtime, strftime

import requests
from twython import Twython
from flickrapi import shorturl
from PIL import Image
from io import BytesIO

############# GLOBALS ##############
# Remember to ``source secrets.sh``!
CONSUMER_KEY = os.environ['TWITTER_CONSUMER_KEY']
CONSUMER_SECRET = os.environ['TWITTER_CONSUMER_SECRET']
ACCESS_TOKEN = os.environ['TWITTER_ACCESS_TOKEN']
ACCESS_TOKEN_SECRET = os.environ['TWITTER_ACCESS_SECRET']
####################################

twitter = Twython(
    CONSUMER_KEY,
    CONSUMER_SECRET,
    ACCESS_TOKEN,
    ACCESS_TOKEN_SECRET
)


# https://github.com/molly/twitterbot_framework/blob/master/bot.py#L57-L62
def log(message):
    path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    with open(os.path.join(path, "birbybot.log"), 'a+') as f:
        t = strftime("%d %b %Y %H:%M:%S", gmtime())
        f.write("\n" + t + " " + message)


with open('plover_1530909825.json', 'r') as readfile:
    photos = json.load(readfile)

photo = random.choice(photos)

title = photo['title']
photographer = photo['ownername']
shorturl = shorturl.url(photo['id'])

message = f'{title} by {photographer} {shorturl} #birbybot'

filename = 'temp.jpg'
r = requests.get(photo['url_o'], stream=True)

if r.status_code == 200:
    with open(filename, 'wb') as image:
        for chunk in r:
            image.write(chunk)

img = open('temp.jpg', 'rb')
response = twitter.upload_media(media=img)
twitter.update_status(status=message, media_ids=[response['media_id']])
os.remove(filename)
log(message)
