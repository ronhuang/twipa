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
import logging
import tweepy
from google.appengine.ext import deferred
from models import get_image_blob, add_image, create_profile, add_profile, monitor_profile
import sensitive


auth = tweepy.BasicAuthHandler(sensitive.username, sensitive.password)
api = tweepy.API(auth)


class UserHandler(webapp.RequestHandler):

  def post(self):
    id = self.request.get('id')

    try:
      user = api.get_user(id=id)
      p = add_profile(user)
      monitor_profile(p)
    except tweepy.TweepError:
      r = api.rate_limit_status()
      if r.remaining_hits == 0:
        logging.error("Hourly limit reached %s/%s" % (r.remaining_hits, r.hourly_limit))
      else:
        logging.error("Cannot fetch profile for id %s" % (id))


class FriendHandler(webapp.RequestHandler):

  def post(self):
    id = self.request.get('id')

    try:
      for user in tweepy.Cursor(api.friends, id=id).items():
        # This may take a while, better defer them.
        deferred.defer(add_profile, user)
    except tweepy.TweepError:
      r = api.rate_limit_status()
      if r.remaining_hits == 0:
        logging.error("Hourly limit reached %s/%s" % (r.remaining_hits, r.hourly_limit))
      else:
        logging.error("Cannot fetch friends for id %s" % (id))


def main():
  actions = [
      ('/twitter/get-user-status', UserHandler),
      ('/twitter/get-friends-statuses', FriendHandler),
      ]
  application = webapp.WSGIApplication(actions, debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
