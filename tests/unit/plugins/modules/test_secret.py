# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import secret


def test_secret_update_value(api, run):
    items = []

    @api.route("GET", "/v1/secrets")
    def lst(q, b):
        return 200, {"secrets": items}

    @api.route("POST", "/v1/secrets")
    def create(q, b):
        items.append({"id": "s1", "key": b["key"].lower()})
        return 200, {"secret": items[-1]}

    @api.route("PATCH", "/v1/secrets/s1")
    def update(q, b):
        return 200, {}

    assert run(secret, dict(key="API_KEY", value="x"))["changed"]
    assert not run(secret, dict(key="API_KEY", value="x", update_value="on_create"))["changed"]
    r = run(secret, dict(key="API_KEY", value="s3cr3t-value"))
    assert r["changed"] and "s3cr3t-value" not in str(r)
