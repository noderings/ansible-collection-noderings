# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import (
    game_server,
    game_server_backup,
    game_server_database,
)

GS_ID = "5e4d3c2b-1111-2222-3333-444455556666"


def game_api(api, phase="GAME_SERVER_PHASE_READY"):
    state = {"servers": {}, "power": "offline", "vars": {"MAX_PLAYERS": "10"}, "image": "img:17", "backups": [], "dbs": []}

    def server(**extra):
        s = dict(id=GS_ID, name="survival", planId="plan-1", templateId="egg-mc", gameName="Minecraft", phase=phase,
                 allocationIp="203.0.113.20", allocationPort=25565)
        s.update(extra)
        return s

    @api.route("GET", "/v1/game-servers:order-games")
    def games(q, b):
        return 200, {"games": [{"id": "egg-mc", "name": "Minecraft", "eula": True}, {"id": "egg-vh", "name": "Valheim"}]}

    @api.route("POST", "/v1/game-servers")
    def create(q, b):
        assert b["templateId"] == "egg-mc" and b["acceptEula"] is True and b["idempotencyKey"]
        state["servers"][GS_ID] = server(name=b["name"])
        return 200, {"id": GS_ID}

    @api.route("GET", "/v1/game-servers")
    def lst(q, b):
        return 200, {"gameServers": list(state["servers"].values())}

    @api.route("GET", "/v1/game-servers/([^/:]+)")
    def get(q, b, gid):
        if gid not in state["servers"]:
            return 404, {"code": 5, "message": "not found"}
        return 200, state["servers"][gid]

    @api.route("DELETE", "/v1/game-servers/([^/:]+)")
    def delete(q, b, gid):
        state["servers"].pop(gid, None)
        return 200, {}

    @api.route("POST", "/v1/game-servers/([^/:]+):rename")
    def rename(q, b, gid):
        state["servers"][gid]["name"] = b["name"]
        return 200, {}

    @api.route("GET", "/v1/game-servers/([^/:]+)/resources")
    def resources(q, b, gid):
        return 200, {"state": state["power"]}

    @api.route("POST", "/v1/game-servers/([^/:]+):power")
    def power(q, b, gid):
        state["power"] = {"start": "running", "stop": "offline", "restart": "running"}[b["signal"]]
        return 200, {}

    @api.route("GET", "/v1/game-servers/([^/:]+)/startup")
    def startup(q, b, gid):
        return 200, {"variables": [{"envVariable": k, "serverValue": v} for k, v in state["vars"].items()], "dockerImage": state["image"],
                     "dockerImages": [{"name": "Java 17", "image": "img:17"}, {"name": "Java 21", "image": "img:21"}]}

    @api.route("PUT", "/v1/game-servers/([^/:]+)/startup")
    def setvar(q, b, gid):
        state["vars"][b["key"]] = b["value"]
        return 200, {}

    @api.route("PUT", "/v1/game-servers/([^/:]+)/docker-image")
    def setimg(q, b, gid):
        state["image"] = b["dockerImage"]
        return 200, {}

    @api.route("GET", "/v1/game-servers/([^/:]+)/backups")
    def backups(q, b, gid):
        return 200, {"backups": state["backups"]}

    @api.route("POST", "/v1/game-servers/([^/:]+)/backups")
    def mkbackup(q, b, gid):
        state["backups"].append({"uuid": "b1", "name": b["name"], "isSuccessful": True, "isLocked": False, "completedAt": "2026-11-23T00:00:00Z"})
        return 200, state["backups"][-1]

    @api.route("POST", "/v1/game-servers/([^/:]+)/backups/([^/:]+):lock")
    def lock(q, b, gid, bid):
        bk = next(x for x in state["backups"] if x["uuid"] == bid)
        bk["isLocked"] = not bk["isLocked"]
        return 200, {}

    @api.route("DELETE", "/v1/game-servers/([^/:]+)/backups/([^/:]+)")
    def rmbackup(q, b, gid, bid):
        state["backups"] = [x for x in state["backups"] if x["uuid"] != bid]
        return 200, {}

    @api.route("GET", "/v1/game-servers/([^/:]+)/databases")
    def dbs(q, b, gid):
        return 200, {"databases": [dict(d, password="") for d in state["dbs"]]}

    @api.route("POST", "/v1/game-servers/([^/:]+)/databases")
    def mkdb(q, b, gid):
        d = {"id": "7", "name": "s1_" + b["database"], "username": "u1", "host": "203.0.113.30", "port": 3306,
             "connectionsFrom": b["remote"], "password": "pw-1"}
        state["dbs"].append(d)
        return 200, d

    @api.route("POST", "/v1/game-servers/([^/:]+)/databases/([^/:]+):rotate")
    def rotate(q, b, gid, did):
        return 200, {"password": "pw-2"}

    return state


ORDER = dict(name="survival", plan_id="plan-1", game="minecraft", accept_eula=True, state="running")


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


def test_database_password_only_on_create(api, run):
    game_api(api)
    run(game_server, ORDER)
    r = run(game_server_database, dict(game_server="survival", name="luckperms"))
    assert r["changed"] and r["database"]["password"] == "pw-1"
    r = run(game_server_database, dict(game_server="survival", name="luckperms"))
    assert not r["changed"] and "password" not in r["database"]
    r = run(game_server_database, dict(game_server="survival", name="luckperms", rotate_password=True))
    assert r["changed"] and r["database"]["password"] == "pw-2"
