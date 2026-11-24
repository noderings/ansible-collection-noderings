# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import game_server, game_server_backup
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.game_server_fakeapi import ORDER, GS_ID, game_api


def test_backup_lock_and_delete(api, run):
    state = game_api(api)
    run(game_server, ORDER)
    r = run(game_server_backup, dict(game_server="survival", name="pre", locked=True))
    assert r["changed"] and r["backup"]["is_locked"]
    assert not run(game_server_backup, dict(game_server="survival", name="pre", locked=True))["changed"]
    r = run(game_server_backup, dict(game_server="survival", name="pre", state="absent"))
    assert r["failed"] and "locked" in r["msg"]
    r = run(game_server_backup, dict(game_server=GS_ID, name="pre", state="absent", locked=False))
    assert r["changed"] and state["backups"] == []
