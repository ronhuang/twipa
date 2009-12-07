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
import os
from google.appengine.ext.webapp import template
from google.appengine.api.labs import taskqueue
from models import Profile
import logging


_AVAILABLE_SIZES = frozenset(['original', 'bigger', 'normal'])


class MainHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write('Hello world!')


class TrackHandler(webapp.RequestHandler):

  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'view', 'track.html')
    self.response.out.write(template.render(path, None))

  def post(self):
    id = self.request.get('id')

    if len(id) > 0:
      t = taskqueue.Task(url='/twitter/get-user-status', params={'id': id})
      taskqueue.Queue('twitter').add(t)

      t = taskqueue.Task(url='/twitter/get-friends-statuses', params={'id': id})
      taskqueue.Queue('twitter').add(t)

    self.redirect('/track')


class ViewHandler(webapp.RequestHandler):

  def get(self):
    profiles = Profile.all()

    template_values = {
      'profiles': profiles,
      'dummy': 'Hello',
      }

    path = os.path.join(os.path.dirname(__file__), 'view', 'view.html')
    self.response.out.write(template.render(path, template_values))


class ImageHandler(webapp.RequestHandler):

  def get(self):
    path = self.request.path[len('/profile_image/'):]
    sid, revision, size = path.split('/')
    id = 0

    try:
      id = int(sid)
    except TypeError:
      logging.error("ID incorrect %s" % sid)
      self.error(404)
      return

    if size not in _AVAILABLE_SIZES:
      logging.warning("id:%s, revision:%s, size:%s" % (id, revision, size))
      self.error(404)
      return

    # TODO: handle revision

    q = Profile.gql("WHERE id = :id "
                    "ORDER BY modified_at DESC",
                    id=id)
    p = q.get()

    if p is None or p.image is None:
      logging.warning("id:%s, revision:%s, size:%s" % (id, revision, size))
      self.error(404)
      return

    i = p.image
    blob = None
    if size in 'original':
      blob = i.original
    elif size in 'bigger':
      blob = i.bigger
    elif size in 'normal':
      blob = i.normal

    if blob is None:
      # Default pictures doesn't have original.
      blob = i.normal

    if blob is None:
      logging.warning("C id:%s, revision:%s, size:%s" % (id, revision, size))
      self.error(404)
      return

    self.response.headers['Content-Type'] = 'image/jpeg'
    self.response.out.write(blob)


def main():
  actions = [
      ('/', MainHandler),
      ('/track', TrackHandler),
      ('/view', ViewHandler),
      (r'/profile_image/.*', ImageHandler),
      ]
  application = webapp.WSGIApplication(actions, debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
