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


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from django.utils import simplejson
from google.appengine.api import urlfetch
import datetime
import logging


_TWITTER_PROPERTIES = frozenset(['id', 'name', 'screen_name', 'created_at',
                                 'location', 'description', 'url',
                                 'followers_count', 'friends_count',
                                 'favourites_count', 'statuses_count',
                                 'profile_image_url'])


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

    for p in _TWITTER_PROPERTIES:
      if self[p] != other[p]:
        diff += 1

    if other.modified_at is None or other.modified_at >= self.modified_at:
      return diff
    else:
      return -diff


def create_profile_from_json(raw):
  data = simplejson.loads(raw)

  profile = Profile(
    id = data['id'],
    name = data['name'],
    screen_name = data['screen_name'],
    # Sat Dec 05 22:32:04 +0000 2009
    created_at = datetime.datetime.strptime(data['created_at'], "%a %b %d %H:%M:%S +0000 %Y"),
    location = data['location'],
    description = data['description'],
    url = data['url'],
    followers_count = data['followers_count'],
    friends_count = data['friends_count'],
    favourites_count = data['favourites_count'],
    statuses_count = data['statuses_count'],
    profile_image_url = db.Link(data['profile_image_url']),
    )

  return profile


def create_image_from_normal_url(normal):
  ext = normal[len(normal)-4:] # assuming the extension has only 3 characters
  base = normal[:len(normal)-len('_normal.xxx')]

  original = base + ext
  bigger = base + '_bigger' + ext

  result = urlfetch.fetch(normal)
  if result.status_code != 200:
    logging.error(normal)
    return None
  normal_blob = db.Blob(result.content)

  result = urlfetch.fetch(original)
  if result.status_code != 200:
    logging.error(original)
    return None
  original_blob = db.Blob(result.content)

  result = urlfetch.fetch(bigger)
  if result.status_code != 200:
    logging.error(bigger)
    return None
  bigger_blob = db.Blob(result.content)

  return Image(
    original = original_blob,
    normal = normal_blob,
    bigger = bigger_blob,
    )


class UserHandler(webapp.RequestHandler):

  def post(self):
    id = self.request.get('id')
    url = "http://twitter.com/users/show.json?id=%s" % (id)

    result = urlfetch.fetch(url)
    if result.status_code != 200:
      # TODO: error handling.
      logging.error("Cannot fetch profile for id %s" % (id))
      return

    remote_profile = create_profile_from_json(result.content)

    query = Profile.gql("WHERE id = :id "
                        "ORDER BY modified_at DESC",
                        id=id)
    local_profile = query.get()

    if local_profile is None or local_profile != remote_profile:
      # Populate image reference
      image = create_image_from_normal_url(remote_profile.profile_image_url)
      image.put()

      remote_profile.image = image
      remote_profile.modified_at = datetime.datetime.utcnow()
      remote_profile.put()


class FriendHandler(webapp.RequestHandler):

  def post(self):
    id = self.request.get('id')
    url = "http://twitter.com/friends/ids/%s.json" % (id)

    result = urlfetch.fetch(url)
    if result.status_code != 200:
      # TODO: error handling.
      logging.error("Cannot fetch friends for id %s" % (id))
      return

    friends = simplejson.loads(result.content)
    q = taskqueue.Queue('query-status')
    for f in friends:
      q.add(taskqueue.Task(url='/twitter/get-user-status', params={'id': f}))


def main():
  actions = [
      ('/twitter/get-user-status', UserHandler),
      ('/twitter/get-friends-ids', FriendHandler),
      ]
  application = webapp.WSGIApplication(actions, debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
