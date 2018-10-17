## Slide 1
### Building a Twitter Image Bot with Flickr and Google Cloud Platform

Hello, what's up GDG San Francisco? How's everyone's DevFest going?

My name is Rachel Ramsay and I'll be showing you how to build a Twitter image bot with Flickr and Google Cloud Platform, particularly the Cloud Vision API.

I hope you come away from this talk with the inspiration to build something that makes you feel good.

Twitter is a site that can be a conduit for upsetting news, hard conversations, and harassment.

Yet I have not logged off.

But I do try to make my timeline a happier place by interspersing positive content.

## Slide 2
### What do you want to see more often?

Think about what would make the good chemical spray in your brain, and then build it.

One account I love, @BirdPerHour, tweeted a few photos of plovers and their babies.

Which made me tweet,

## Slide 3
### _[Read]_ "What if I made a bot that exclusively posted pictures of plovers and their babies?"

Programming already gives you spurts of dopamine when you figure something out, but combining that with photos of fluffy baby birds? I highly recommend it as a side project.

Also, what you build doesn't have to post to Twitter! Twitter is introducing a vetting process for apps; I'll cover that plus alternatives to Twitter at the end.

## Slide 4
### Working with Intellectual Property

When I started this project, I had to think about how I would approach copyrighted material. Some people figure they'll get some DMCA takedowns and maybe their bot will be suspended, and that's fine. But,

## Slide 5
### _[Read]_ Crediting photographers and not reposting copyrighted images were priorities for me.

As a follower of image bots, I'm often frustrated by not knowing how to find more work by whoever created what I'm seeing, so I wanted my bot to link back to sources.

## Slide 6
### How will you find images?

This is a non-exhaustive list of APIs that you can use to find Creative Commons-licensed images.

I started with Flickr because I was familiar with it as an end-user; it's what I turn to when I need a Creative Commons-licensed image for a zine or whatever.

I may add more sources for my bot to pull from in the future. Unsplash is a particularly good source for aesthetic photos. Their license is incredibly permissive: you can use Unsplash photos in commercial projects without credit; you just can't scrape their photos to make your own Unsplash.

## Slide 7
### Searching Flickr

So, with the dream of seeing more pictures of baby plovers on my timeline, I turned to Flickr.

This is a simplified code snippet that uses the flickrapi Python module by Sybren Stuvel; we'll see a little bit more of this in the demo, but of course you don't have to write in Python or use Flickr in your own project.

"Flickr," I said, "show me baby plovers."

## Slide 8
### That's not a bird...

While Flickr _did_ show me baby plovers, it also showed me this turtle. So, that's a problem.

## Slide 9
### _[Read]_ Flickr returns photos that contain the search term in their title, description, or tags.

and this image is titled "Threatened _baby_ bog turtle," and its description includes the word "plover".

## Slide 10
### ...threatened and endangered species that occur in Connecticut, including the threatened bog turtle, piping plover, and Puritan tiger beetle...

If you were building a tiger image bot, this turtle might appear in those search results, too!

## Slide 11
### I can sort Flickr results by relevance, but how do I know when results stop being relevant?

There wasn't a good solution within the Flickr API to make sure that my bot never tweeted a non-bird&ndash;photo by accident.

Now, there weren't _that_ many search results. I _could_ have sorted the birds from the non-birds by hand.

But I didn't do that.

## Slide 12
### Cloud Vision API

Ultimately, I decided to take all of the results returned by Flickr and run them through Cloud Vision API.

## Slide 13
### Features

Cloud Vision API is great because it already knows what a bird is. It already knows what a lot of things are. Think about how you can use this feature set:

* You can detect &ndash; but not _recognize_ &ndash; faces, including the emotions displayed on those faces. So it can tell you, "That's a face that looks nervous," but not, "That's Rachel's face."
* You can detect landmarks that are in the image, such as the Golden Gate Bridge.
* There's also logo detection.
* Or if you have a photo of a storefront, you can read the name of the store from its sign.
* Plus, there's a more robust OCR endpoint for documents.
* Safe Search Detection is crucial for making sure your bot doesn't tweet anything gory or racy.
* Image Properties can tell you the dominant colors in the images, which would come in handy if you wanted to tweet images centered around a particular color aesthetic.
* Crop Hints can help you format images for different aspect ratios suited to different social media platforms.
* Web Detection can do things like find websites that use the image, or give you URLs to visually similar images. So it's like reverse image search.
* Label Detection and Object Localization are the features my bot uses, so we'll dig into those.

## Slide 14
### Client Libraries

There are client libraries for C#, Go, Java, Node, PHP, Python, and Ruby, or you can call the REST API directly.

## Slide 15
### Label Detection

Label detection evaluates the image as a whole.

## Slide 16
### Definitely not a bird

When we run our baby box turtle through label detection, we know it's not a bird.

(The numbers are confidence scores.)

But because label detection evaluates the image as a whole, it can miss things.

## Slide 17
### But this _is_ a bird

For this image, label detection only detects sand; is misses the adorable piping plover chick that I can plainly see with my human eyes.

For Cloud Vision to see the plover, I turned to Object Localization.

## Slide 18
### Object Localization

In addition to detecting objects, object localization does some rudimentary categorization.

## Slide 19
### Well, it's definitely something...

Sometimes it does recognize the object as a bird, but for this photo, it was like, "Eh, I think we got an animal here."

But I can use that bounding poly to crop the image and run it through label detection again.

## Slide 20
### Crop to object and detect labels again

This time, label detection recognized the plover as a bird, which is good enough for me.

However,

## Slide 21
### _[Read]_ Detecting and labeling objects is not bulletproof.

It's a good strategy, but it can still fail.

## Slide 22
### Doesn't look like anything to me

Nature has this dastardly thing called camouflague.

## Slide 23
### After cropping

In this case, we get further away from correct classification when we crop: now Cloud Vision API detects no animal (a.k.a., fauna) at all.

## Slide 24
### Cloud AutoML Vision

Enter Cloud AutoML for Vision. It makes it easier to train your own image classification models.

## Slide 25
### _[Read]_ I have not trained a model to distinguish camouflaged fauna from flora...yet.

But side projects make for great excuses to learn the technologies you're interested in.

## Slide 26
### Cloud Datastore

In addition to being able to programmatically differentiate bird from non-bird, I needed a way to keep track of the image's metadata, where it's located, and when I last tweeted it, so that my bot doesn't repeat itself.

Using Cloud Datastore for a Twitter bot is like hitting a fly with a sledge hammer, but I chose it because I wanted to learn it.

## Slide 27
### _[Read]_ Cloud Datastore is a NoSQL database.

Now that it's built on top of Firestore, it's strongly consistent.

But because Firestore is in Datastore mode, real-time updates are not supported, which is fine for this project.

## Slide 28
### Data Model

When I create Photo entities, I store Flickr's API results plus a few additional properties like `is_bird` and `last_tweeted`.

Later I can add Unsplash API results as Photo entities, which will have different properties, and that's fine.

## Slide 29
### Composite Indexes

Since I want to ask the datastore for photos of birds that I haven't tweeted recently, I need to create a composite index. Adding composite indexes is easy: you define your indexes a YAML file and deploy it with the gcloud tool. My YAML file looks like what this helpful error message suggested!

## Slide 30
### Birds, But Make It Spooky

In this demo, we're going to be iteratively building up a simple script that will find and tweet photos of bats.

_[Switch to Visual Studio Code]_