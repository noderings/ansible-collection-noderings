# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import ssh_key


def test_ssh_key_ignores_comment_and_replaces_on_change(api, run):
    keys = []

    @api.route("GET", "/v1/ssh-keys")
    def lst(q, b):
        return 200, {"sshKeys": keys}

    @api.route("POST", "/v1/ssh-keys")
    def create(q, b):
        keys.append({"id": "k%d" % len(keys), "name": b["name"], "publicKey": b["publicKey"]})
        return 200, {"sshKey": keys[-1]}

    @api.route("DELETE", "/v1/ssh-keys/([^/]+)")
    def delete(q, b, kid):
        keys[:] = [k for k in keys if k["id"] != kid]
        return 200, {}

    assert run(ssh_key, dict(name="me", public_key="ssh-ed25519 AAAA me@a"))["changed"]
    assert not run(ssh_key, dict(name="me", public_key="ssh-ed25519 AAAA other\n"))["changed"]
    r = run(ssh_key, dict(name="me", public_key="ssh-ed25519 BBBB me@a"))
    assert r["changed"] and len(keys) == 1 and keys[0]["publicKey"].startswith("ssh-ed25519 BBBB")
