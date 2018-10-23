## Setup

* Turn on Caffeine.
* Turn on Do Not Disturb.
* Open Chrome Guest Window from user portrait.
* In Visual Studio Code, open `bats.py`.
* Open integrated terminal with `control+backtick`.
* `cd rachel-src/birbybot/slides`
* `reveal-md slides.md`
* `Control+shift+backtick` to open new integrated terminal.
* `cd rachel-src/birbybot/`
* `source start.sh`
* Quit unneeded programs.
* Maximize Chrome and `cmd+shift+f` to hide address bar.

## Slide 0
### Building a Twitter Bot with Flickr and GCP

Hello, what's up GDG San Francisco? How's everyone's DevFest going so far?

My name is Rachel Ramsay, and today I'll be sharing what I learned while building a Twitter image bot with the Flickr API and Google Cloud Platform, particularly the Cloud Vision API.

I should warn you that I'm on call right now, so apologies in advance if I get paged.

I love birdwatching, and my journey into bot-making began when I tweeted a simple question.

## Slide 1
### A Simple Question

"What if I made a bot that exclusively posted pictures of plovers and their babies?"

(If you don't know what a plover is, it's a shorebird, and its babies are adorable.)

## Slide 2
### @beachbirbys

I ended up making beachbirbys, for all your beach bird baby needs.

Today, I'm going to tell you what I learned while building beachbirbys, and share some resources for building your own bot.

I hope that you come away with the inspiration and guidance to build something that makes you feel good.

## Slide 3
### A Simple Plan

My goals for this bot were simple:

1. Get pictures of plover babies from Flickr.
2. Post those pictures to Twitter.
3. Feel the good chemical spraying everywhere in my brain.

## Slide 4
### Problem #1

When I started this project, I had to decide how I would approach copyrighted material. Some people's approach is more blasé &mdash; they figure they'll get some DMCA takedowns and maybe their bot will be suspended; whatever happens, happens.

But, for me, crediting photographers and not reposting copyrighted images were priorities.

As a follower of image bots, I'm often frustrated by not knowing how to find more work by whoever created what I'm seeing, so I wanted my bot to link back to its sources.

## Slide 5
### Solution #1

I chose Flickr as my image source because of its strong support for attribution and Creative Commons licenses.

## Slide 6
### Searching Flickr

So, with the goal of seeing more pictures of baby plovers on my timeline, I said to Flickr, "Show me baby plovers."

And I got back...

## Slide 7
### That's not a bird...

A baby turtle.

Flickr's API _did_ return baby plovers, but it also returned this turtle. As cute as this turtle is, I don't want my bot to post it.

So, why did it appear in my results?

## Slide 8
### _[Read]_ Flickr returns photos that contain the search term in their title, description, or tags

This image is titled "_Baby_ bog turtle," and its description includes the word "plover".

## Slide 9
### ...threatened and endangered species that occur in Connecticut, including the threatened bog turtle, piping plover, and Puritan tiger beetle...

If you were building a tiger image bot, this turtle might appear in those search results, too!

So, now we have a problem.

## Slide 10
### Problem #2

There wasn't a good solution within the Flickr API to make sure that my bot never tweeted a non-bird photo by accident.

Now, there weren't _that_ many search results. I _could_ have sorted the birds from the non-birds by hand.

But I didn't do that, because when given a choice between doing the thing myself and spending many hours making the computer do the thing, I will always choose the latter.

## Slide 11
### Cloud Vision API

Ultimately, I decided to take all of the results returned by Flickr and run them through Cloud Vision API.

Cloud Vision API is great because it already knows what a bird is; it already knows what a lot of things are because its image recognition models are already trained.

## Slide 12
### Approach #1

Label detection evaluates the image as a whole.

When we run our baby box turtle through label detection, we know it's not a bird.

## Slide 13
### Definitely not a bird

(Those numbers are confidence scores.)

But because label detection evaluates the image as a whole, it can miss things.

## Slide 14
### But this is a bird

For this image, label detection only sees sand; it misses the adorable piping plover chick that I can plainly see with my human eyes.

In order for Cloud Vision API to see the plover, I turned to Object Localization.

## Slide 15
### Approach #2

In addition to detecting objects, object localization does some rudimentary categorization.

## Slide 16
### Well, it's definitely something...

Sometimes object localization _does_ recognize an object as a bird, but for our photo of a baby plover on the beach, it was like, "Eh, I think we got an animal here."

But I can use that bounding poly to crop the image and run it through label detection again.

## Slide 17
### Solution #2

When I do _that_, label detection recognizes the plover as a bird, which is good enough for my bot to use it.

That said,

## Slide 18
### Problem #3

Detecting and labeling objects is not bulletproof.

It's a good strategy, but it can still fail.

## Slide 19
### Doesn't look like anything to me

Nature has this thing called camouflage.

While my human eyes can pick out the spotted sandpiper hatchlings, Cloud Vision API is only vaguely sensing the presence of fauna.

## Slide 20
### After cropping

When I crop this time, I actually get further away from correct classification: now Cloud Vision API detects no animal presence at all; we've lost that fauna label.

## Slide 21
### Cloud AutoML Vision

Enter Cloud AutoML for Vision, which is designed to simplify training your own image classification models.

## Slide 22
### Solution #3?

I have not trained a model to distinguish camouflaged fauna from flora...yet.

I turned to Cloud Vision precisely because I didn't want to train my own models.

How deep does this rabbit hole go?

## Slide 23
### Birds, But Make It Spooky

In this demo, we're going to build up a simple script that will find and tweet photos of bats because it's almost Halloween!

_[Cmd+tab to switch to Visual Studio Code.]_

## Demo

This script will:

1. Search Flickr for bat photos.
2. Classify each search result as either bat or non-bat.
3. Store image data in Cloud Datastore, a NoSQL database.

_[Control+g **116** Enter]_

The first thing we're doing is instantiating our clients and searching Flickr for bats _[line 132]_.

Our search string will be the word "bat"...

The license parameter is selecting various Creative Commons licenses...

We've got safe search turned on...

And I've picked dates that I hope will surface some good cases.

Then we'll take these results and use them to create entities for Cloud Datastore _[line 147]_.

Cloud Datastore's data objects are called entities. Entities have Keys made up of a Kind and a Name. We're going to call this kind of entity Photos, and we're going to make the name part of the key their source API plus the UUID from that API.

Everything returned by Flickr, we dump into this entitiy, then
we add a few extra properties.

`is_classified` allows us to have a two-step process where we can write entities to the datastore before classifying them.

Flickr has a few different image sizes, but they were introduced at different times, so not all photos come in all sizes &mdash; that's why we have a helper function to pick the best download url available.

Entities of the same kind do not need to have the same properties, and an entity's values for a given property do not all need to be of the same data type. This gives me the flexibility to add results from a different image API later on. Those Photo entities will have different properties, and that's fine.

_[Control+g **303** Enter]_

So, we'll get our search results for the word "bat," then we'll turn those results into entities.

We're also going to open our photos so that we know what it is we have to classify.

Once we have our entities, we _could_ write them to the datastore, then come back later and ask the datastore for entities where is_classified is False, but we'll just classify them first and write them after that.

####_Your code block should look like_

```
    pp = pprint.PrettyPrinter()
    
    photos = search_flickr("bat")
    entities = photos_to_entities(photos)
    
    pp.pprint(entities)
    show_photos(entities)
```

_[Command+s to save.]_

_[Control+backtick to switch focus to terminal: `python bats.py`]_

Flickr gave us some cute bats, but it also gave us some non-bats. That's why we need Cloud Vision API.

_[Control+backtick to switch focus to editor.]_

_[Command+/ to comment out `pp.pprint(entities)` and `show photos`.]_

Before we go over how we'll classify our photos as bat or non-bat, let's look at the Vision API response.

_[Uncomment `classify as resp only`.]_

####_Your code block should look like_

```
    pp = pprint.PrettyPrinter()

    photos = search_flickr("bat")
    entities = photos_to_entities(photos)
    
    # pp.pprint(entities)
    # show_photos(entities)

    classify_as_resp_only(["bat"], entities)
```

_[Command+s to save.]_

_[Control+backtick to switch focus to terminal: `python bats.py`]_

So, we have our label annotations: _[read labels]_.

And we have our localized object annotations: _[read names]_.

_[Control+backtick to switch focus to editor.]_

_[Comment out `classify as resp only`]_

_[Uncomment `classify as` and `with ds client` block.]_

####_Your code block should look like_

```
    pp = pprint.PrettyPrinter()

    photos = search_flickr("bat")
    entities = photos_to_entities(photos)
    
    # pp.pprint(entities)
    # show_photos(entities)

    # classify_as_resp_only(["bat"], entities[3:6])

    classify_as(["bat"], entities)
    with ds_client.batch():
        ds_client.put_multi(entities)
```

_[Command+s to save.]_

During this step, we're going to classify our Flickr results and write them to the datastore.

_[Control+g **189** Enter]_

This function, `classify as`, iterates over the entities. For each entity, it downloads the image from Flickr and puts that image on a request to detect labels and localize objects _[line 197]_.

Hopefully, we get back label annotations and object localizations.

Sometimes the response does not include the features we asked for &mdash; especially object localizations because sometimes the API can't detect any objects in the image &mdash; hence the if blocks _[line 209]_.

We take any labels and object names that we get and put them in a set.

Most Cloud Vision API features return verticies in pixels, but for some reason the object localization feature returns verticies that have been normalized between zero and 1. We transform those normalized verticies into coordinates that we can crop to later.

Now we come to our helper function, `is_a` _[line 223]_. It takes a list of terms &mdash; in our case, we'll pass a list with only one element, the word "bat" &mdash; as well as a collection of labels. `is_a` checks if "bat" is in that collection of labels and returns a boolean.

So, if it's not a bat, but we did get back crop coordinates, we're going to:

* crop the image to just that object _[line 227]_
* convert the cropped image from a Pillow Image to a Vision Image _[line 232]_
* and then make a new request to the Vision API to label our cropped image _[line 235]_

Hopefully, we get back new labels _[line 240]_. Then we:

* add them to our set
* check if we've found a bat yet
* if we have found a bat, we won't crop to the rest of the objects. We don't want to call the API if we don't have to.

Now that we've done what we can to identify the image as either bat or non-bat, we update the entity _[line 249]_ and mark it as having been classified.

Moment of truth...

_[Control+backtick to switch focus to terminal: `python bats.py`]_

Great, we found {2} bats.

Time to tweet!

_[Control+backtick to switch focus to editor.]_

_[Control+g **303** Enter]_

_[Comment out **everything** except initial `pp = pprint.PrettyPrinter()`]_

_[Uncomment `query =`, `query.add`, `bats =`, `pp.print`, `bat = random`, `tweet photo entity`]_

We're going to ask the datastore for all the bat photos. Then we're going to choose one and tweet it. For us, loading a few entities into memory is not a big deal, but we could also make the query keys-only, then randomly choose the key and get just that entitity.

####_Your code block should look like this_

```
    pp = pprint.PrettyPrinter()

    # photos = search_flickr("bat")
    # entities = photos_to_entities(photos)
    
    # pp.pprint(entities)
    # show_photos(entities)

    # classify_as_resp_only(["bat"], entities[3:6])

    # classify_as(["bat"], entities)
    # with ds_client.batch():
        # ds_client.put_multi(entities)

    # Get bats from Cloud Datastore.
    query = ds_client.query(kind="Photo")
    query.add_filter("is_bat", "=", True)
    bats = list(query.fetch())
    pp.pprint(bats)

    # Time to tweet!
    bat = random.choice(bats)
    tweet_photo_entity(bat)
```

_[Control+g **266** Enter]_

First, we're gonna write a message. What's the hashtag for this event? _[If possible, add after `#HappyHalloween`. I think it's `#devfest18`.]_

Then we're gonna upload the photo to Twitter _[line 281]_, and attach it and our message to our tweet _[line 283]_.

Finally, we'll record when we tweeted in the datastore _[line 294]_. We can use this with a composite index to only pull bat photos that we haven't tweeted recently.

_[Command+s to save.]_

_[Control+backtick to switch focus to terminal: `python bats.py`]_

_[Command+tab to Chrome. Next slide!]_

Let's see how it looks...

## Slide 24
### @beachbirbys

_[Command-click link to open in new tab, command-2 to switch to that tab.]_

Awesome!

## Slide 25
### Composite Indexes

During the demo, I mentioned composite indexes.

If I want to ask the datastore for photos of birds &mdash; or bats &mdash; that I haven't tweeted recently, I need to create a composite index.

Adding composite indexes to your datastore is easy: you define your indexes in a YAML file and deploy it with the gcloud tool. My YAML file looks like what this helpful error message suggested!

Shoutout to the engineers who wrote an error message that tells you how to fix itself!

## Slide 26
### Problem #4

Where am I going to host my scripts?

I have one that goes looking for new results, one that classifies unclassified entities, and one that tweets.

## Slide 27
### Solution #4

I'm currently hosting my bot at PythonAnyhwere.com, which is a great online IDE and web hosting service. If you use Python, check it out!

## Slide 28
### What do you want to see?

Maybe you're not obsessed with birds. But I bet there's something you want to see. So, what are you going to build?

## Slide 29
### Image Sources

This is a non-exhaustive list of APIs that you can use to find Creative Commons-licensed images.

Unsplash is a particularly good source for aesthetic photos. Their license is incredibly permissive: you can use Unsplash photos in commercial projects without credit; you just can't scrape their photos to create your own Unsplash.

## Slide 30
### Cloud Vision API Features

Think about what you can build with this feature set:

* You can detect &ndash; but not _recognize_ &ndash; faces, including the emotions displayed on those faces.
* You can detect landmarks in an image, such as the Golden Gate Bridge.
* There's also logo detection.
* Or if you have a photo of a storefront, you can read the name of the store from its sign.
* There's a more robust OCR endpoint for documents.
* Safe Search Detection is crucial for making sure that your bot doesn't tweet anything gory or racy.
* Image Properties can tell you the dominant colors in an image, which would come in handy if you were building something centered around a particular color aesthetic.
* Crop Hints can help you format images for different aspect ratios suited to different social media platforms.
* Web Detection can do things like find websites that use an image, or give you URLs to visually similar images. So, it's like reverse image search.

## Slide 31
### What about video?

Flickr can return not just photos but also video. If you are dedicated to tweeting only the choicest cute animal _videos_, there are Google Cloud Platform APIs to help with that, too!

Cloud Video Intelligence API has a label detection feature that's similar to Cloud Vision API's.

There's also Explicit Content Detection, which is like Safe Search Detection.

One of the challenges of working with video is programatically detecting "good clips" &mdash; you know, visually interesting, not too long. Cloud Video Intelligence has a Shot Change Detection feature, which can help you roll your own clipping strategy.

Speech Transcription is currently in beta.

You can combine those transcripts with the Natual Language API, or the Translation API.

## Slide 32
### More GCP

One of the reasons why I used Cloud Datastore was that I was already on Google Cloud Platform due to Cloud Vision. It's worth exploring the rest of what Google has to offer.

You may have noticed that our bats-to-Twitter script downloaded photos locally. That's not required -- you could get the image from its URL and use the response body as bytes to instantiate your image every time you wanted to work with it, or you can store images with Cloud Storage.

As for hosting your scripts, App Engine has a cron service, while Cloud Scheduler was announced back in July and is currently in alpha.

## Slide 33
### Twitter

At the end of July, Twitter started requiring developers to answer a questionnaire about how they plan to use Twitter's API and its data before permitting developers to create an API key.

Currently, Twitter asks:

1. What is the core use case, intent, or purpose for your use of Twitter's APIs?
2. Do you intend to analyze Tweets, Twitter users, or their content? If so, share details about the analyses you plan to conduct and the methods or techniques you plan to use.
3. Does your use case involve Tweeting, Retweeting, or liking content? If so, share how you will interact with Twitter users or their content.
4. How will Twitter data be displayed to users of your solution? If you plan to display Twitter content off of Twitter, explain how and where Tweets and Twitter content will be displayed to users of your product or service. Will individual Tweets and Twitter content be displayed, or will information about Tweets or Twitter content be displayed in aggregate?

This _is_ a hoop to jump through, but you can do it.

(Also, Flickr already had a similar requirement, so I had my "Please just let me post cute animal photos" spiel ready.)

But maybe you're done with Twitter...

## Slide 34
### Mastodon

Mastodon is an open source, decentralized social network. It has a few nice design features &mdash; for example, you can't search arbitrary strings, so while you can still find posts via hashtags, it's harder for people to search something they want to fight about.

Plus, there's a Mastodon instance just for bots called BotsIn.Spaaaace!

(My next mini-project will probably be updating beachbirbys to crosspost to Mastodon.)

Tumblr is a visually-focused social network with an API, so that's a possibility, too.

## Slide 35
### What are you going to build?

Thank you for listening. I hope that you feel inspired to mash together some APIs to create something that makes you smile.

## Slide 36
### Photo Credits

Thanks to the photographers who took these turtle, bird, and bat photos!

## Slide 37
### Rachel Ramsay

I am Rachel Ramsay, and I care about birds the normal amount.

You can find me on Twitter at rachelbuilds, and you can find today's slides and code on my GitHub.

Thank you.