# Birbybot
_It makes the [good chemical](https://lifestyle.clickhole.com/9-inspiring-photos-that-will-make-your-brain-spray-the-1825122796) spray everywhere._

Birbybot is the code behind [@beachbirbys](https://www.twitter.com/beachbirbys), the Twitter bot dedicated to bringing ~~me~~ you Creative Commons&ndash;licensed photos of baby shorebirds.

Birbybot is built with:

* Python 3.6
* Flickr and [flickrapi](https://pypi.org/project/flickrapi/)
* [Twython](https://pypi.org/project/twython/)
* [Cloud Firestore in Datastore mode](https://cloud.google.com/datastore/docs/quickstart)
* [Cloud Vision API](https://cloud.google.com/vision/docs/all-samples)

It is hosted on [PythonAnywhere](https://www.pythonanywhere.com), where it tries to stay out of the tarpit.

## Files
* `flickr_to_datastore.py`
Should be run once a month via cron, but I don't have it set up anywhere.
* `classify_images.py`
Should be run after new images are added to datastore.
* `tweet.py`
Chooses image from datastore and tweets it. Cron job runs daily.