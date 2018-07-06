#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from flickrapi import FlickrAPI
from pprint import pprint

############# GLOBALS ##############
# Remember to ``source secrets.sh``!
FLICKR_PUBLIC = os.environ['FLICKR_KEY']
FLICKR_SECRET = os.environ['FLICKR_SECRET']
####################################

flickr = FlickrAPI(FLICKR_PUBLIC, FLICKR_SECRET, format="parsed-json")

# https://www.flickr.com/services/api/flickr.photos.search.html
# https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html

text = "plover babies"
license = "1,2,3,4,5,6,7,8,9,10"
sort = "relevance"
media = "photos"
extras = "license,owner_name,url_o"

birbys = flickr.photos.search(
    text=text,
    license=license,
    sort=sort,
    media=media,
    extras=extras
    )
photos = birbys['photos']
pprint(photos)
