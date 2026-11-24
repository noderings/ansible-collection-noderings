# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import game_server
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.game_server_fakeapi import ORDER, game_api


def test_order_installs_and_starts(api, run):
    state = game_api(api)
    r = run(game_server, ORDER)
    assert r["changed"] and not r.get("failed")
    assert r["game_server"]["primary_port"] == 25565
    assert state["power"] == "running"
    again = run(game_server, ORDER)
    assert not again["changed"]


def test_order_requires_eula(api, run):
    game_api(api)
    r = run(game_server, dict(ORDER, accept_eula=False))
    assert r["failed"] and "accept_eula" in r["msg"]
    assert not any(m == "POST" for m, p in api.writes())


def test_check_mode_orders_nothing(api, run):
    game_api(api)
    r = run(game_server, ORDER, check_mode=True)
    assert r["changed"]
    assert api.writes() == []


def test_failed_install_is_reported(api, run):
    game_api(api, phase="GAME_SERVER_PHASE_FAILED")
    r = run(game_server, ORDER)
    assert r["failed"] and "No payment was taken" in r["msg"]


def test_settings_power_and_delete(api, run):
    state = game_api(api)
    run(game_server, ORDER)
    r = run(game_server, dict(name="survival", environment={"MAX_PLAYERS": 20}, docker_image="img:21", new_name="creative", state="offline"))
    assert r["changed"]
    assert state["vars"]["MAX_PLAYERS"] == "20" and state["image"] == "img:21" and state["power"] == "offline"
    assert r["game_server"]["name"] == "creative"
    bad = run(game_server, dict(name="creative", environment={"NOPE": 1}))
    assert bad["failed"] and "does not exist" in bad["msg"]
    bad = run(game_server, dict(name="creative", docker_image="img:99"))
    assert bad["failed"]
    r = run(game_server, dict(name="creative", state="absent"))
    assert r["changed"] and state["servers"] == {}
    assert not run(game_server, dict(name="creative", state="absent"))["changed"]


def test_game_change_needs_permission(api, run):
    game_api(api)
    run(game_server, ORDER)
    r = run(game_server, dict(name="survival", game="Valheim"))
    assert not r["changed"] and not r.get("failed")
    assert not any(p.endswith(":changeGame") for m, p in api.writes())
