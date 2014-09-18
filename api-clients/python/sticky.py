#!/usr/bin/env python
# vim: tabstop=4 softtabstop=4 shiftwidth=4 textwidth=80 smarttab expandtab
#
# Copyright (c) 2014 Moises Silva <moises.silva@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import os
import datetime
import requests
import argparse
import json
import inspect
from StringIO import StringIO

class StickyNotes(object):
    """
    See http://sayakb.github.io/sticky-notes/pages/api/
    """
    urlfmt = '{site}/api/json'
    parameters = [
        'expire',
        'language',
        'version',
        'theme',
    ]

    def __init__(self, site):
        if not site.startswith('http'):
            site = 'http://' + site
        self.site = site
        self.url = self.urlfmt.format(site=self.site)
        expire_values = StringIO()
        self._parameter_values('expire', buf=expire_values)
        self._expire_values = [int(x) for x in expire_values.getvalue().split()]

    def _parameter_values(self, parameter, buf=None):
        parameters = '/parameter/{parameter}'
        endpoint = parameters.format(parameter=parameter)
        r = self._get_request(endpoint)
        return self._handle_response(r, buf)

    def parameter_values(self, parameter):
        return _parameter_values(parameter)

    def list(self):
        endpoint = '/list/all'
        r = self._get_request(endpoint)
        return self._handle_response(r)

    def _paste_req_prepare_expire(self, expire):
        expire = int(expire)
        if expire <= 0:
            return 0
        expire = expire * 60
        exp_index = min(range(len(self._expire_values)),
                    key=lambda i: abs(self._expire_values[i]-expire))
        return self._expire_values[exp_index]

    def _paste_req_prepare_private(self, private):
        if private:
            return True
        else:
            # docs say that the parameter should not be
            # included at all if the paste is not private
            return None

    def paste(self, fname,
            req_title=None,
            req_language=None,
            req_password=None,
            req_private=None,
            req_expire=30,
            req_project=None):
        fargs = locals()
        endpoint = '/create'
        params = {
            'language': 'text',
            'title': os.path.basename(fname),
        }

        try:
            fp = open(fname, 'r')
            params['data'] = fp.read() # ugh, how about some cap hu?
        except Exception, e:
            sys.write(sys.stderr, 'Failed to open paste file {}: {}'.format(fname, e))
            return

        for name, val in fargs.iteritems():
            if not val or not name.startswith('req_'):
                continue
            param_func = '_paste_req_prepare_{}'.format(name[4:])
            if hasattr(self, param_func):
               pf = getattr(self, param_func)
               val = pf(val)
               if not val:
                   continue
            params[name[4:]] = val

        r = self._post_request(endpoint, params)
        self._handle_response(r)

    def _post_request(self, endpoint, params):
        uri = self.url + endpoint
        r = requests.post(uri, data=params)
        return r

    def _get_request(self, endpoint):
        uri = self.url + endpoint
        r = requests.get(uri)
        return r

    def _paste_details(self, paste):
        paste_uri = '/show/{paste}'
        endpoint = paste_uri.format(paste=paste)
        r = self._get_request(endpoint)
        res = json.loads(r.text)
        if 'error' in res['result']:
            print 'Error retrieving paste {paste}: {error}'.format(paste=paste, error=res['result']['error'])
            return None
        return res['result']

    def _handle_response(self, response, buf=None):
        def report(val):
            if buf:
                buf.write(val)
                buf.write('\n')
            else:
                print val
        res = json.loads(response.text)
        if 'error' in res['result']:
            report('Error: {}'.format(res['result']['error']))
        elif 'values' in res['result']:
            for val in res['result']['values']:
                report(val)
        elif 'pastes' in res['result']:
            tabfmt = '{:<15} {:<15} {:<15} {:<15} {:<10} {:<10} {}'
            report(tabfmt.format('Id', 'Author', 'Title',
                    'Project', 'Language', 'Date', 'URL'))
            sep = [('-' * 10)] * 7
            report(tabfmt.format(*sep))
            def val(value):
                return value if value else 'n/a'
            for paste in res['result']['pastes']:
                r = self._paste_details(paste)
                if r:
                    pastedate = datetime.datetime.fromtimestamp(int(r['timestamp'])).strftime('%Y/%m/%d')
                    report(tabfmt.format(r['id'], val(r['author']),
                            val(r['title']), val(r['project']),
                            r['language'], pastedate,
                            self.site + '/' + r['id']))
        elif 'id' in res['result']:
            report(self.site + '/' + res['result']['id'])
        else:
            report(res['result'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', help='base site url (e.g http://server.org)', required=True)
    parser.add_argument('--parameter',
            help='List available values for a given parameter',
            choices=StickyNotes.parameters)
    parser.add_argument('--list', help='List all pastes', action='store_true')
    parser.add_argument('--paste', help='Paste the contents of a file', metavar='FILE')
    for m in inspect.getmembers(StickyNotes):
        if m[0] != 'paste':
            continue
        for arg in inspect.getargspec(m[1]).args:
            if not arg.startswith('req_'):
                continue
            argname = arg[4:]
            arghelp = 'Set the {} option in the paste request'.format(argname)
            parser.add_argument(
                    '--' + argname,
                    help=arghelp)
        break

    args = parser.parse_args()

    sticky = StickyNotes(args.site)
    if args.parameter:
        sticky.parameter_values(args.parameter)
    elif args.list:
        sticky.list()
    elif args.paste:
        sticky.paste(args.paste,
                req_title=args.title,
                req_language=args.language,
                req_password=args.password,
                req_expire=args.expire,
                req_project=args.project)

