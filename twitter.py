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
  location = db.StringProperty()
  description = db.StringProperty()
  url = db.LinkProperty()
  followers_count = db.IntegerProperty(required=True)
  friends_count = db.IntegerProperty(required=True)
  favourites_count = db.IntegerProperty(required=True)
  statuses_count = db.IntegerProperty(required=True)
  image_url = db.LinkProperty()

  # My properties.
  image = db.ReferenceProperty(Image)
  modified_at = db.DateTimeProperty(required=True)


class UserHandler(webapp.RequestHandler):

  def post(self):
    pass


class FriendHandler(webapp.RequestHandler):

  def post(self):
    pass


def main():
  actions = [
      ('/twitter/get-user-status', UserHandler),
      ('/twitter/get-friends-ids', FriendHandler),
      ]
  application = webapp.WSGIApplication(actions, debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
