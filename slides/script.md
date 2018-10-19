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
### Building a Twitter Image Bot with Flickr and Google Cloud Platform

Hello, what's up GDG San Francisco? How's everyone's DevFest going?

My name is Rachel Ramsay, and today I'll be showing you how to build a Twitter image bot with the Flickr API and Google Cloud Platform, particularly the Cloud Vision API.

I hope that you come away from this talk with the inspiration to build something that makes you feel good.

Twitter is a site that can be a conduit for upsetting news, hard conversations, and harassment.

Yet I have not logged off.

But I do try to make my timeline a happier place by interleaving positive content.

## Slide 1
### What do you want to see more often?

Think about what would make the good chemical spray in your brain, and then build it.

One account I love, @BirdPerHour, tweeted a few photos of plovers and their babies.

Which inspired me to tweet,

## Slide 2
### _[Read]_ "What if I made a bot that exclusively posted pictures of plovers and their babies?"

Thus beginning my journey into bot making.

Also, what you build doesn't have to post to Twitter! Twitter recently introduced a vetting process for apps, and I'll cover that, plus alternatives to Twitter, later in the presentation.

## Slide 3
### Working with Intellectual Property

When I started this project, I had to think about how I would approach copyrighted material. Some people's approach is more blase &ndash; they figure they'll get some DMCA takedowns and maybe their bot will be suspended; whatever happens, happens.

But, for me,

## Slide 4
### _[Read]_ Crediting photographers and not reposting copyrighted images were priorities

As a follower of image bots, I'm often frustrated by not knowing how to find more work by whoever created what I'm seeing, so I wanted my bot to link back to its sources.

## Slide 5
### How will you find images?

This is a non-exhaustive list of APIs that you can use to find Creative Commons-licensed images.

I started with Flickr because I was familiar with it as an end-user. In the future, I may add more sources for my bot to pull from.

(Unsplash is a particularly good source for aesthetic photos. Their license is incredibly permissive: you can use Unsplash photos in commercial projects without credit; you just can't scrape their photos to create your own Unsplash.)

## Slide 6
### Searching Flickr

So, with the goal of seeing more pictures of baby plovers on my timeline, I turned to Flickr.

This is a simplified code snippet that uses the flickrapi Python module by Sybren Stuvel; we'll see a bit more of this in the demo, but of course you don't have to write in Python or use Flickr in your own project.

"Flickr," I said, "show me baby plovers."

And Flickr said...

## Slide 7
### That's not a bird...

"How about a baby turtle?"

Flickr's API _did_ return baby plovers, but it also returned this turtle. As cute as this turtle is, I don't want my bot to post it.

Why did it appear in my results?

## Slide 8
### _[Read]_ Flickr returns photos that contain the search term in their title, description, or tags

and this image is titled "Baby bog turtle," and its description includes the word "plover".

## Slide 9
### ...threatened and endangered species that occur in Connecticut, including the threatened bog turtle, piping plover, and Puritan tiger beetle...

If you were building a tiger image bot, this turtle might appear in those search results, too!

So, now we have a problem.

## Slide 10
### I can sort Flickr results by relevance, but how do I know when results stop being relevant?

There wasn't a good solution within the Flickr API to make sure that my bot never tweeted a non-bird photo by accident.

Now, there weren't _that_ many search results. I _could_ have sorted the birds from the non-birds with my human eyes.

But I didn't do that, because when given a choice between doing the thing myself and spending many hours making the computer do the thing, I will always choose the latter.

## Slide 11
### Cloud Vision API

Ultimately, I decided to take all of the results returned by Flickr and run them through Cloud Vision API.

Cloud Vision API is great because it already knows what a bird is; it already knows what a lot of things are because its image recognition models are already trained.

## Slide 12
### Features

Think about what you can build with this feature set:

* You can detect &ndash; but not _recognize_ &ndash; faces, including the emotions displayed on those faces. So it can tell you, "That's a face, and it looks nervous," but not, "That's Rachel's face."
* You can detect landmarks in an image, such as the Golden Gate Bridge.
* There's also logo detection.
* Or if you have a photo of a storefront, you can read the name of the store from its sign.
* There's a more robust OCR endpoint for documents.
* Safe Search Detection is crucial for making sure that your bot doesn't tweet anything gory or racy.
* Image Properties can tell you the dominant colors in an image, which would come in handy if you wanted to build something centered around a particular color aesthetic.
* Crop Hints can help you format images for different aspect ratios suited to different social media platforms.
* Web Detection can do things like find websites that use an image, or give you URLs to visually similar images. So, it's like reverse image search.
* Label Detection and Object Localization are the features that my bot uses, so we'll dig into those in a second.

## Slide 13
### Client Libraries

Cloud Vision API has client libraries for a variety of languages, or you can call the REST API directly.

## Slide 14
### Label Detection

Label detection evaluates the image as a whole.

When we run our baby box turtle through label detection, we know it's not a bird.

## Slide 15
### Definitely not a bird

(Those numbers are confidence scores.)

But because label detection evaluates the image as a whole, it can miss things.

## Slide 16
### But this _is_ a bird

For this image, label detection only sees sand; it misses the adorable piping plover chick that I can plainly see with my human eyes.

In order for Cloud Vision API to see the plover, I turned to Object Localization.

## Slide 17
### Object Localization

In addition to detecting objects, object localization does some rudimentary categorization.

Sometimes it _does_ recognize the object as a bird, but for our photo of a baby plover on the beach, it was like, "Eh, I think we got an animal here."

## Slide 18
### Well, it's definitely something...

But I can use that bounding poly to crop the image and run it through label detection again.

## Slide 19
### Crop to object and detect labels again

When I do _that_, label detection recognizes the plover as a bird, which is good enough for my bot to use it.

That said,

## Slide 20
### _[Read]_ Detecting and labeling objects is not bulletproof.

It's a good strategy, but it can still fail.

## Slide 21
### Doesn't look like anything to me

Nature has this thing called camouflage.

While my human eyes can pick out the spotted sandpiper hatchlings, Cloud Vision API is only vaguely sensing the presence of fauna.

## Slide 22
### After cropping

When I crop this time, I actually get further away from correct classification: now Cloud Vision API detects no animal presence at all; we've lost that fauna label.

## Slide 23
### Cloud AutoML Vision

Enter Cloud AutoML for Vision, which is designed to simplify training your own image classification models.

## Slide 24
### _[Read]_ I have not trained a model to distinguish camouflaged fauna from flora...yet.

But side projects do make for great excuses to start learning the technologies that you're interested in, so maybe I will in the future!

## Slide 25
### Cloud Datastore

In addition to being able to programmatically differentiate bird from non-bird, I needed a way to keep track of the images' metadata, their location, and when I last tweeted them, so that my bot doesn't repeat itself too often.

Using Cloud Datastore for a Twitter bot is like hitting a fly with a sledge hammer, but I chose it because I wanted to learn it.

## Slide 26
### _[Read]_ Cloud Datastore is a NoSQL database.

Now that it's built on top of Firestore, it's strongly consistent.

But because Firestore is in Datastore mode, real-time updates are not supported &ndash; which is fine for this project.

## Slide 27
### Data Model

When I create Photo entities, I store Flickr's API results plus a few additional properties like `is_bird` and `last_tweeted`.

Later on, I can add results from a different API as Photo entities, which will have different properties, and that's fine.

## Slide 28
### Composite Indexes

Since I want to ask the datastore for photos of birds that I haven't tweeted recently, I need to create a composite index. Adding composite indexes to your datastore is easy: you define your indexes in a YAML file and deploy it with the gcloud tool. My YAML file looks like what this helpful error message suggested!

## Slide 29
### Birds, But Make It Spooky

In this demo, we're going to build up a simple script that will find and tweet photos of bats because it's almost Halloween!

_[Estimated elapsed time: 10 minutes.]_

_[Cmd+tab to switch to Visual Studio Code.]_

## Demo

Let's see...we're using flickrapi, the Google Cloud client library, Pillow (the Python Image Library), and Twython.

Got some helper functions...

And the first thing we're doing is instantiating our clients and searching Flickr for bats.

Our search string will be `"bats"`.

The license parameter is selecting various Creative Commons licenses.

We've got safe_search turned on.

And we're going to grab five interesting cases.

And to these results, we'll add a few additional properties.

Cloud Datastore Entities have Keys made up of a Kind and a Name. We're going to call this kind of entity Photos, and we're going to make the keys their source API &mdash; in this case, Flickr &mdash; plus the UUID from that API.

Flickr has a few different image sizes, but they were introduced at different times, so not all photos come in all sizes &mdash; that's why we have a helper function to pick the best download url available.

_[Control+g 304 Enter]_

So, we'll get our search results for the word "bat," and turn those results into entities.

We're also going to open our photos so that we know what we have to classify.

We _could_ write these entities to the datastore and then come back later to retrieve entities where is_classified is False, but we'll classify them first and write them after that.

_[Your code block should look like]_

```
    pp = pprint.PrettyPrinter()
    
    photos = search_flickr("bat")
    entities = photos_to_entities(photos)
    pp.pprint(entities)
    
    show_photos(entities)
```

_[Command+s to save.]_

_[Control+backtick to switch focus to terminal: `python bats.py`]_

Here are our lovely entities.

Flickr gave us some cute bats in trees, but it also gave us some monks! Time for Cloud Vision API to get to work.

_[Control+backtick to switch focus to editor.]_

_[Arrow down and command+/ to comment out `pp.pprint(entities)` and `show photos`.]_

Before we go over how we'll classify our photos as bat or non-bat, let's look at a our response from the Vision API.

_[Arrow down and uncomment `classify as resp only`.]_

_[Your code block should look like]_

```
    pp = pprint.PrettyPrinter()

    photos = search_flickr("bat")
    entities = photos_to_entities(photos)
    # pp.pprint(entities)

    # show_photos(entities)

    classify_as_resp_only(["bat"], entities[3:6])
```

_[Command+s to save.]_

_[Control+backtick to switch focus to terminal: `python bats.py`]_

So, we've got our label annotations: _[read labels]_.

(_[If possible]_ And our localized object annotations: _[read names]_.)

_[Control+backtick to switch focus to editor.]_

_[Comment out `classify as resp only`]_

_[Uncomment `classify as`]_

_[Control+g 169 Enter]_

Okay, so this function, `classify as` iterates over the entities. For each entity, it:

* downloads the image locally
* loads it into memory and creates it as a Vision Image

_[line 197]_ We put that image on a request to the Vision API to detect labels and localize objects.

We get back label annotations, like what's in the terminal. At this point, we haven't gotten a "bat" label.

We also get back our object localizations. Again, Cloud Vision doesn't know we've got a bat.

Sometimes the response does not include the features we ask for &mdash; this is particuarly common when we ask for object localization, hence the if blocks _[line 209]_.

We take all those labels and object names and put them in a set, and we also transform those normalized verticies into coordinates we can crop to.

(We're storing the coordinates as tuples in a set because sometimes we'll get back the same coordinates identified with multiple names, and we don't want to crop the same object multiple times.)

Now we come to our helper function, `is_a` _[line 224]_. This takes a list of terms &mdash; in our case, we'll pass a list with only one element, the word `"bat"` &mdash; as well as a collection of labels. `is_a` checks if "bat" is in that collection of labels.

So, if it's not a bat, but we did get back crop coordinates, we're going to:

* crop the image to just that object _[line 228]_
* convert the crop from a Pillow Image to a Vision Image _[line 233]_
* and ask the API to detect labels again.

Now that we have new labels _[line 241]_:

* we'll add them to our set
* check if we've found a bat yet
* and if we have found a bat, we won't crop to the rest of the objects. Let's not call the API if we don't have to.

Now we've done what we can to sort the image as bat or non-bat, so we update the entity _[line 250]_ and mark it as having been classified.

_[Control+g 313 Enter]_

During this step, we're also going to write the entities to the datastore.

_[Arrow down and uncomment `with ds client` block.]_

_[Your code block should look like]_

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

_[Command+tab to Terminal: `python bats.py`]_

Great, we found {2} bats.

Time to tweet!

_[Control+backtick to switch focus to editor.]_

_[Comment out **everything** except initial `pp = pprint.PrettyPrinter()`]_

_[Arrow down and uncomment `query =`, `query.add`, `bats =`, `pp.print`]_

We're going to ask the datastore for all the bat photos. Then we're going to choose one and tweet it. For us, pulling a few entities is not a big deal, but we could also make the query keys-only, then randomly choose the key and get just that entitity.

_[Uncomment `tweet photo entity`]_

_[Your code block should look like this]_

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
    tweet_photo_entity(random.choice(bats))
```

_[Control+g 266 Enter]_

First, we're gonna write a message. What's the hashtag for this event? _[If possible, add after `#HappyHalloween`.]_

Then we're gonna upload the photo to Twitter _[line 282]_, and then attach it and our message to our tweet.

Finally, we'll record our tweet in the datastore _[line 294]_. We can use this with a composite index to only pull bat photos that we haven't tweeted recently.

_[Command+s to save.]_

_[Command+tab to Terminal: `python bats.py`]_

_[Command+tab to Chrome. Next slide!]_

Let's see how it looks...

## Slide 30
### @beachbirbys

_[Command-click link to open in new tab, command-2 to switch to that tab.]_

Awesome!