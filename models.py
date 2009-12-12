#!/usr/bin/env python
#
# Copyright (c) 2009 Ron Huang
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


from google.appengine.ext import db
from google.appengine.api import urlfetch
from datetime import datetime
import logging
from google.appengine.runtime import DeadlineExceededError
from google.appengine.api.urlfetch import DownloadError
from urlparse import urlsplit


_BLOB_MAXIMUM_SIZE = 10485760 - 1024 # reserve 1K for others


class Image(db.Model):
  name = db.StringProperty(required=True)
  modified_at = db.DateTimeProperty(required=True)
  url = db.LinkProperty(required=True)
  content_type = db.StringProperty(required=True)
  content = db.BlobProperty(required=True)


class Profile(db.Model):
  # Twitter's properties.
  id = db.IntegerProperty(required=True)
  name = db.StringProperty(required=True)
  screen_name = db.StringProperty(required=True)
  created_at = db.DateTimeProperty(required=True)
  location = db.StringProperty(default="")
  description = db.StringProperty(default="")
  url = db.StringProperty(default="")
  followers_count = db.IntegerProperty(required=True)
  friends_count = db.IntegerProperty(required=True)
  favourites_count = db.IntegerProperty(required=True)
  statuses_count = db.IntegerProperty(required=True)
  profile_image_url = db.LinkProperty()

  # My properties.
  original_image = db.ReferenceProperty(Image, collection_name="profile_original_set")
  bigger_image = db.ReferenceProperty(Image, collection_name="profile_bigger_set")
  normal_image = db.ReferenceProperty(Image, collection_name="profile_normal_set")
  mini_image = db.ReferenceProperty(Image, collection_name="profile_mini_set")
  modified_at = db.DateTimeProperty()


  def __cmp__(self, other):
    # Compare Twitter's properties only.
    # Profile without modified_at field is always newer.
    diff = 0

    if self.id != other.id:
      diff += 1
    if self.name != other.name:
      diff += 1
    if self.screen_name != other.screen_name:
      diff += 1
    if self.created_at != other.created_at:
      diff += 1
    if self.location != other.location:
      diff += 1
    if self.description != other.description:
      diff += 1
    if self.url != other.url:
      diff += 1
    if self.followers_count != other.followers_count:
      diff += 1
    if self.friends_count != other.friends_count:
      diff += 1
    if self.favourites_count != other.favourites_count:
      diff += 1
    if self.statuses_count != other.statuses_count:
      diff += 1
    if self.profile_image_url != other.profile_image_url:
      diff += 1

    if other.modified_at is None or other.modified_at >= self.modified_at:
      return diff
    else:
      return -diff


class Monitor(db.Model):
  profile_id = db.IntegerProperty(required=True)
  modified_at = db.DateTimeProperty(required=True, default=datetime.min)
  explicit = db.BooleanProperty(required=True, default=False) # True if monitored explicitly.


def monitor_profile(profile):
  # Monitor profile.
  query = Monitor.gql("WHERE profile_id = :profile_id",
                      profile_id=profile.id)
  m = query.get()

  if m and m.explicit:
    # Nothing else to do.
    return
  elif m:
    m.explicit = True
  else:
    m = Monitor(
      profile_id = profile.id,
      explicit = True,
      )

  try:
    m.put()
  except:
    logging.error("Failed to operate Monitor, id:%s" % profile.id)


def add_image(url):
  url = url.encode('utf-8')

  # Get image information (HEAD)
  try:
    result = urlfetch.fetch(url, method=urlfetch.HEAD)
  except (DeadlineExceededError, DownloadError), e:
    logging.error("Failed to retrieve information for image %s" % url)
    logging.error(e)
    return
  except UnicodeEncodeError, e:
    logging.error("Failed to retrieve information for image %s" % url)
    logging.error(e)
    return

  if result.status_code != 200:
    logging.warning("Failed to retrieve information for image %s" % url)
    return

  try:
    str = result.headers['Last-Modified'] # Thu, 17 Sep 2009 16:33:10 GMT
    last_modified = datetime.strptime(str, '%a, %d %b %Y %H:%M:%S GMT')
  except:
    logging.error("Cannot parse Last-Modified from image %s" % url)
    return

  # Check if already exist.
  q = Image.gql("WHERE url = :url "
                "AND modified_at = :date",
                url=url, date=last_modified)
  image = q.get()

  # Return if image already exist in datastore.
  if image:
    return image

  # Image doesn't exist, create new one.
  # First retrieve the content of the image.
  try:
    result = urlfetch.fetch(url)
  except (DeadlineExceededError, DownloadError), e:
    logging.error("Cannot fetch image %s" % url)
    logging.error(e)
    return

  if result.status_code != 200:
    logging.warning("Cannot fetch image %s" % url)
    return

  length = _BLOB_MAXIMUM_SIZE + 1
  try:
    length = int(result.headers['Content-Length'])
  except:
    logging.error("Cannot parse Content-Length from image %s" % url)
    return

  if length > _BLOB_MAXIMUM_SIZE:
    logging.warning("Image %s too large %s" % (url, length))
    return

  # Parse name of the image.
  try:
    path = urlsplit(url).path.split('/')
    name = path[len(path) - 1]
  except:
    logging.error("Failed to parse name for image %s" % url)
    return

  # Create new Image
  image = Image(
    name = name,
    modified_at = last_modified,
    url = url,
    content_type = result.headers['Content-Type'],
    content = db.Blob(result.content),
    )

  try:
    image.put()
  except Exception, e:
    logging.error("Failed to add image %s to datastore" % url)
    logging.error(str(e))
    return

  return image


def add_profile_images(normal):
  dot_index = normal.rfind('.')
  ext = normal[dot_index:]
  normal_index = normal.rfind('_normal.')

  if (0 <= len('_normal') - dot_index) or (-1 == normal_index):
    # Unusual image url, use same URL for all image...
    logging.warning("Unusual image URL %s" % (normal))

    original_image = add_image(normal)
    bigger_image = add_image(normal)
    normal_image = add_image(normal)
    mini_image = add_image(normal)
  else:
    # Retrieve all version of the profile images.
    base = normal[:normal_index]

    original = base + ext
    bigger = base + '_bigger' + ext
    mini = base + '_mini' + ext

    original_image = add_image(original)
    bigger_image = add_image(bigger)
    normal_image = add_image(normal)
    mini_image = add_image(mini)

  return original_image, bigger_image, normal_image, mini_image


def create_profile(user):
  profile = Profile(
    id = user.id,
    name = user.name,
    screen_name = user.screen_name,
    created_at = user.created_at,
    location = user.location,
    description = user.description,
    url = user.url,
    followers_count = user.followers_count,
    friends_count = user.friends_count,
    favourites_count = user.favourites_count,
    statuses_count = user.statuses_count,
    profile_image_url = db.Link(user.profile_image_url),
    )

  return profile


def add_profile(user, explicit=False):
  remote_profile = create_profile(user)

  query = Profile.gql("WHERE id = :id "
                      "ORDER BY modified_at DESC",
                      id=user.id)
  local_profile = query.get()

  profile = None # either the existing or the created profile.

  if local_profile is None or local_profile != remote_profile:
    # Populate image reference
    url = remote_profile.profile_image_url
    (remote_profile.original_image,
     remote_profile.bigger_image,
     remote_profile.normal_image,
     remote_profile.mini_image) = add_profile_images(url)

    # Populate modified_at.
    remote_profile.modified_at = datetime.utcnow()

    try:
      remote_profile.put()
    except:
      logging.error("Failed to add profile id:%s, screen_name:%s" % (user.id, user.screen_name))
      return

    profile = remote_profile
  else:
    profile = local_profile

  if profile is None:
    return

  # Monitor profile.
  query = Monitor.gql("WHERE profile_id = :profile_id",
                      profile_id=profile.id)
  m = query.get()

  if m:
    # update modified_at
    m.modified_at = datetime.utcnow()
    m.explicit |= explicit
  else:
    m = Monitor(
      profile_id = profile.id,
      modified_at = datetime.utcnow(),
      explicit = explicit,
      )

  try:
    m.put()
  except:
    logging.error("Failed to operate Monitor, id:%s" % profile.id)
