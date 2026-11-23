# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""An in-memory stand-in for the NodeRings API, plugged in where the client opens URLs."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import io
import json
import re

from ansible.module_utils.six.moves.urllib.error import HTTPError
from ansible.module_utils.six.moves.urllib.parse import parse_qs, urlparse


class FakeResponse(object):
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body


class FakeAPI(object):
    """Routes requests to handlers registered by (method, path regex)."""

    def __init__(self):
        self.routes = []
        self.calls = []

    def route(self, method, pattern):
        def deco(fn):
            self.routes.append((method, re.compile("^" + pattern + "$"), fn))
            return fn
        return deco

    def __call__(self, url, method="GET", data=None, headers=None, **kwargs):
        u = urlparse(url)
        query = dict((k, v if len(v) > 1 else v[0]) for k, v in parse_qs(u.query).items())
        body = json.loads(data) if data else None
        self.calls.append((method, u.path, query, body))
        for m, rx, fn in self.routes:
            match = rx.match(u.path)
            if m == method and match:
                status, out = fn(query, body, *match.groups())
                if status >= 400:
                    raise HTTPError(url, status, "error", {}, io.BytesIO(json.dumps(out).encode()))
                return FakeResponse(out)
        raise HTTPError(url, 404, "no route", {}, io.BytesIO(json.dumps({"code": 5, "message": "no route %s %s" % (method, u.path)}).encode()))

    def writes(self):
        return [(m, p) for m, p, q, b in self.calls if m != "GET"]
