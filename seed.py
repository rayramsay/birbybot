#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json

from flickrapi import FlickrAPI

############# GLOBALS ##############
# Remember to ``source secrets.sh``!
FLICKR_PUBLIC = os.environ['FLICKR_KEY']
FLICKR_SECRET = os.environ['FLICKR_SECRET']
####################################

flickr = FlickrAPI(FLICKR_PUBLIC, FLICKR_SECRET, format="parsed-json")

# https://www.flickr.com/services/api/flickr.photos.search.html
# https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html

text = "plover baby"
license = "1,2,3,4,5,6,7,8,9,10"
sort = "relevance"
media = "photos"
extras = "license,owner_name,url_o"

results = flickr.photos.search(
    text=text,
    license=license,
    sort=sort,
    media=media,
    extras=extras
    )

print("Pages: " + str(results['photos']['pages']))
print("Total results: " + str(results['photos']['total']))

photos = results['photos']['photo']

print("Writing results to results.txt")
with open('results.txt', 'w') as outfile:
    json.dump(photos, outfile, indent=4, ensure_ascii=False)
