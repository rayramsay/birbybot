#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from twython import Twython

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

###### NOTE TO FUTURE RACHEL ######
# Make short URLs: https://stuvel.eu/flickrapi-doc/8-shorturl.html

message = "Snowy Plovers near Santa Barbara by Mick Thompson https://www.flickr.com/photos/mickthompson/17911734021/ #birbybot"
photo = open('assets/plovers.jpg', 'rb')
response = twitter.upload_media(media=photo)
twitter.update_status(status=message, media_ids=[response['media_id']])
