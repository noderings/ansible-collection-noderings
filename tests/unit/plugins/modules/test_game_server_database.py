# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import game_server, game_server_database
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.game_server_fakeapi import ORDER, game_api


def test_database_password_only_on_create(api, run):
    game_api(api)
    run(game_server, ORDER)
    r = run(game_server_database, dict(game_server="survival", name="luckperms"))
    assert r["changed"] and r["database"]["password"] == "pw-1"
    r = run(game_server_database, dict(game_server="survival", name="luckperms"))
    assert not r["changed"] and "password" not in r["database"]
    r = run(game_server_database, dict(game_server="survival", name="luckperms", rotate_password=True))
    assert r["changed"] and r["database"]["password"] == "pw-2"
