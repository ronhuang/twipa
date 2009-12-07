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
import datetime
import logging
from google.appengine.runtime import DeadlineExceededError


_BLOB_MAXIMUM_SIZE = 10485760


class Image(db.Model):
  original = db.BlobProperty()
  normal = db.BlobProperty()
  bigger = db.BlobProperty()


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
  image = db.ReferenceProperty(Image)
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


def get_image_blob(url):
  result = None

  try:
    result = urlfetch.fetch(url)
    if result is None or result.status_code != 200:
      logging.warning("Cannot fetch image %s" % url)
      return
  except DeadlineExceededError, e:
    logging.error("Cannot fetch image %s" % url)
    logging.error(e)
    return

  length = _BLOB_MAXIMUM_SIZE + 1
  try:
    length = int(result.headers['Content-Length'])
  except TypeError:
    logging.error("Content-Length is invalid %s" % result.headers['Content-Length'])
    return

  if length > _BLOB_MAXIMUM_SIZE:
    logging.warning("Image %s too large %s" % (url, length))
    return

  return db.Blob(result.content)


def add_image(normal):
  # Check if the image already exist in database.
  query = Profile.gql("WHERE profile_image_url = :piu "
                      "ORDER BY modified_at DESC",
                      piu=normal)
  profile = query.get()
  if profile is not None and profile.image:
    return profile.image

  # New image, add to database.
  original_blob, normal_blob, bigger_blob = None, None, None

  dot_index = normal.rfind('.')
  ext = normal[dot_index:]

  normal_index = normal.rfind('_normal.')
  if (0 <= len('_normal') - dot_index) or (-1 == normal_index):
    # Unusual image url.
    logging.warning("Unusual image URL %s" % (normal))
  else:
    # Retrieve all version of the profile images.
    base = normal[:normal_index]

    original = base + ext
    bigger = base + '_bigger' + ext

    original_blob = get_image_blob(original)
    normal_blob = get_image_blob(normal)
    bigger_blob = get_image_blob(bigger)

  image = Image(
    original = original_blob,
    normal = normal_blob,
    bigger = bigger_blob,
    )
  image.put()

  return image


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


def add_profile(user):
  remote_profile = create_profile(user)

  query = Profile.gql("WHERE id = :id "
                      "ORDER BY modified_at DESC",
                      id=user.id)
  local_profile = query.get()

  if local_profile is None or local_profile != remote_profile:
    # Populate image reference
    image = add_image(remote_profile.profile_image_url)

    remote_profile.image = image
    remote_profile.modified_at = datetime.datetime.utcnow()
    remote_profile.put()
