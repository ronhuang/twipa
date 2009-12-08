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
from google.appengine.api.labs import taskqueue
from datetime import datetime, timedelta
from models import add_profile, Monitor, Profile
import sensitive


auth = tweepy.BasicAuthHandler(sensitive.username, sensitive.password)
api = tweepy.API(auth)


class UserHandler(webapp.RequestHandler):

  def get_existing_profile(self, raw):
    if raw.isdecimal():
      id = int(raw)
      query = Profile.gql("WHERE id = :id",
                          id=id)
      profile = query.get()
    else:
      query = Profile.gql("WHERE screen_name = :screen_name",
                          screen_name=raw)
      profile = query.get()

    return profile

  def is_recently_monitored(self, profile):
    query = Monitor.gql("WHERE profile = :profile",
                        profile=profile)
    m = query.get()
    if m is None:
      return False

    expire_time = m.modified_at + timedelta(minutes=60) # expire in 1 hour.
    return datetime.utcnow() < expire_time

  def post(self):
    id = self.request.get('id')

    # Check if we really need to make request to Twitter.
    profile = self.get_existing_profile(id)
    if profile and self.is_recently_monitored(profile):
      # No need to monitor.
      return

    try:
      user = api.get_user(id=id)
    except tweepy.TweepError:
      r = api.rate_limit_status()
      if r['remaining_hits'] == 0:
        logging.error("Hourly limit reached %s/%s" % (r['remaining_hits'], r['hourly_limit']))
      else:
        logging.error("Cannot fetch profile for id %s" % (id))
    else:
      add_profile(user, True)


class FriendHandler(webapp.RequestHandler):

  def post(self):
    id = self.request.get('id')

    try:
      for user in tweepy.Cursor(api.friends, id=id, retry_count=3).items():
        # This may take a while, better defer them.
        deferred.defer(add_profile, user, False)
    except tweepy.TweepError:
      r = api.rate_limit_status()
      if r['remaining_hits'] == 0:
        logging.error("Hourly limit reached %s/%s" % (r['remaining_hits'], r['hourly_limit']))
      else:
        logging.error("Cannot fetch friends for id %s" % (id))


class MonitorHandler(webapp.RequestHandler):

  def get(self):
    queue = taskqueue.Queue('twitter')
    query = Monitor.gql("WHERE explicit = :explicit",
                        explicit=True)

    for m in query:
      id = m.profile.id

      t = taskqueue.Task(url='/twitter/get-user-status', params={'id': id})
      queue.add(t)

      t = taskqueue.Task(url='/twitter/get-friends-statuses', params={'id': id})
      queue.add(t)


def main():
  actions = [
      ('/twitter/get-user-status', UserHandler),
      ('/twitter/get-friends-statuses', FriendHandler),
      ('/twitter/monitor-users-statuses', MonitorHandler),
      ]
  application = webapp.WSGIApplication(actions, debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
