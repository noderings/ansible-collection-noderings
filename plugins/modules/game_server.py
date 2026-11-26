#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: game_server
short_description: Order and manage NodeRings game servers
version_added: 0.1.0
description:
  - Orders a game server (for example Minecraft or Valheim) from a hosting provider on the NodeRings marketplace,
    keeps its name, startup variables, container image and power state as configured, and deletes it.
  - Choose what to order with O(plan_id), or let the module pick an offer from O(plan_code), O(country) and O(city).
    List the games a plan can run with M(noderings.cloud.game_server_game_info).
  - Game servers are matched by O(name), or by O(id) when given.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
  - noderings.cloud.noderings.wait
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
options:
  name:
    description:
      - Name of the server, 1 to 64 characters. Used to find an existing server, so keep it unique.
      - Required unless O(id) is given.
    type: str
  id:
    description:
      - ID of an existing server.
    type: str
  new_name:
    description:
      - Rename the server found by O(name) or O(id) to this.
    type: str
  state:
    description:
      - V(present) orders the server if needed. V(running) and V(offline) also start or stop it.
      - V(restarted) restarts it. V(absent) deletes it with all its files; billing stops.
    type: str
    choices: [present, running, offline, restarted, absent]
    default: present
  plan_id:
    description:
      - Game-server plan to order. Mutually exclusive with O(plan_code).
    type: str
  region_id:
    description:
      - Region to place the server in. Defaults to the region of the node it lands on.
    type: str
  plan_code:
    description:
      - Marketplace plan code, for example C(SC-GS-4C-8G-50). The module picks an offer in O(country) and O(city).
    type: str
  country:
    description:
      - Country of the offer. Required with O(plan_code).
    type: str
  city:
    description:
      - City of the offer. Required with O(plan_code).
    type: str
  billing_type:
    description:
      - Billing type of the offer when using O(plan_code).
    type: str
    choices: [usage, subscription, free]
  provider:
    description:
      - Only consider offers from this hosting provider, given by its provider ID, its storefront slug
        (for example C(acme-hosting)) or its name (for example C(Acme Hosting), in any case).
      - A name that more than one provider uses fails; give the provider ID or storefront slug then.
      - Without a provider the module picks the best offer from any provider (see O(sort)).
      - Mutually exclusive with O(provider_id).
    type: str
  provider_id:
    description:
      - Only consider offers from this provider.
    type: str
  sort:
    description:
      - How to choose between offers.
    type: str
    choices: [price, rating]
    default: price
  game:
    description:
      - Game to install, by name (for example C(Minecraft)) or by the C(id) from M(noderings.cloud.game_server_game_info).
        Game IDs are specific to the plan's provider.
      - Required when the server is ordered.
    type: str
  allow_game_change:
    description:
      - When O(game) differs from what an existing server runs, change the game in place.
        The server keeps its address, but B(all files, schedules and backups are deleted).
    type: bool
    default: false
  accept_eula:
    description:
      - Accept the game's end-user licence agreement. Required when the game has one.
    type: bool
    default: false
  version:
    description:
      - Game version to install. Only used when the server is ordered; later, set the version variable in O(environment).
    type: str
  environment:
    description:
      - Startup variables, such as the game version or player limit. Only the keys listed are managed.
    type: dict
    default: {}
  docker_image:
    description:
      - Container image the game runs in. Must be one of the game's images (see M(noderings.cloud.game_server_info)).
    type: str
"""

EXAMPLES = r"""
- name: A Minecraft server in Frankfurt
  noderings.cloud.game_server:
    name: survival
    plan_code: SC-GS-4C-8G-50
    country: Germany
    city: Frankfurt
    billing_type: subscription
    game: Minecraft
    accept_eula: true
    environment:
      MAX_PLAYERS: "20"
    state: running
  register: mc

- name: Tell players where to connect
  ansible.builtin.debug:
    msg: "{{ mc.game_server.primary_ip }}:{{ mc.game_server.primary_port }}"

- name: Stop it
  noderings.cloud.game_server:
    name: survival
    state: offline
"""

RETURN = r"""
game_server:
  description: The server. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 5e4d3c2b-0000-0000-0000-000000000000
    name: survival
    game_name: Minecraft
    variant: Paper
    phase: ready
    power_state: running
    primary_ip: 203.0.113.20
    primary_port: 25565
    plan_code: SC-GS-4C-8G-50
    provider_name: Example Hosting
    region_city: Frankfurt
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.gameserver import gs_view, live_power, resolve_game_server, UUID_RE
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import NoOfferError, find_offers, no_offer_message
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    NodeRingsModule,
    TimeoutError_,
    Waiter,
    is_not_found,
    new_uuid,
    noderings_argument_spec,
)


class GameServer(NodeRingsModule):

    def __init__(self, module):
        super(GameServer, self).__init__(module)
        self.p = module.params
        self.waiter = Waiter(self.p["wait_timeout"], interval=5)

    def choose_plan(self):
        p = self.p
        if p["plan_id"]:
            return p["plan_id"], p["region_id"]
        try:
            offers, located = find_offers(self.client, p["plan_code"], p["country"], p["city"], billing_type=p["billing_type"],
                                          asset_type="game_server", provider_id=p["provider_id"], sort=p["sort"], provider=p["provider"])
        except (NodeRingsError, NoOfferError) as e:
            self.fail("looking up offers for %s" % p["plan_code"], e)
        if not offers:
            self.module.fail_json(msg=no_offer_message(p["plan_code"], p["country"], p["city"], p["billing_type"], located,
                                                       p["provider"] or p["provider_id"]))
        return offers[0]["plan_id"], offers[0]["region_id"]

    def resolve_game(self, plan_id):
        games = self.call("listing games", self.client.list_order_games, plan_id)
        ref = self.p["game"]
        hit = next((g for g in games if g.get("id") == ref), None) or next(
            (g for g in games if (g.get("name") or "").lower() == ref.lower()), None)
        if not hit:
            self.module.fail_json(msg="game %s is not available on this plan; available: %s" % (
                ref, ", ".join(sorted(g.get("name") or "" for g in games))))
        if hit.get("eula") and not self.p["accept_eula"]:
            self.module.fail_json(msg="%s has an end-user licence agreement; set accept_eula=true to accept it" % hit.get("name"))
        return hit

    def wait_installed(self, gs_id):
        last = {}

        def check():
            gs = self.client.get_game_server(gs_id)
            last["gs"] = gs
            phase = gs.get("phase")
            if phase == "GAME_SERVER_PHASE_ERROR":
                raise RuntimeError("game server %s failed to install: %s. It was paid for; its game can be reinstalled or changed"
                                   % (gs_id, gs.get("lastError") or "no reason given"))
            if phase == "GAME_SERVER_PHASE_FAILED":
                raise RuntimeError("game server %s failed to install: %s. No payment was taken; it can only be deleted"
                                   % (gs_id, gs.get("lastError") or "no reason given"))
            return phase == "GAME_SERVER_PHASE_READY", gs

        try:
            return self.waiter.wait("game server %s to install" % gs_id, check)
        except (RuntimeError, TimeoutError_, NodeRingsError) as e:
            self.module.fail_json(msg=str(e), changed=True, game_server=gs_view(last.get("gs")))

    def power(self, gs_id, want):
        c = self.client
        state = (self.call("reading power state", c.get_game_server_resources, gs_id) or {}).get("state")
        if want == "restarted":
            self.call("restarting", c.power_game_server, gs_id, "restart")
            want = "running"
        elif state == want:
            return False
        elif live_power(state) != want:
            self.call("changing power state", c.power_game_server, gs_id, "stop" if want == "offline" else "start")
        if self.p["wait"]:
            self.call("waiting for the power state", self.waiter.wait, "game server to be %s" % want,
                      lambda: ((c.get_game_server_resources(gs_id) or {}).get("state") == want, None))
        return True

    def apply_settings(self, gs, check):
        """Rename, startup variables and container image. Returns True when something changed."""
        c = self.client
        p = self.p
        gs_id = gs["id"]
        changed = False
        if p["new_name"] and p["new_name"] != gs.get("name"):
            changed = True
            if not check:
                self.call("renaming", c.rename_game_server, gs_id, p["new_name"])
        if p["environment"] or p["docker_image"]:
            startup = self.call("reading startup settings", c.get_game_server_startup, gs_id) or {}
            values = dict((v.get("envVariable"), v.get("serverValue")) for v in startup.get("variables") or [])
            for key, value in sorted(p["environment"].items()):
                if key not in values:
                    self.module.fail_json(msg="startup variable %s does not exist for this game; it has: %s" % (key, ", ".join(sorted(values))))
                if str(value) != (values.get(key) or ""):
                    changed = True
                    if not check:
                        self.call("setting %s" % key, c.update_game_server_startup_variable, gs_id, key, str(value))
            if p["docker_image"] and p["docker_image"] != startup.get("dockerImage"):
                images = [i.get("image") for i in startup.get("dockerImages") or []]
                if p["docker_image"] not in images:
                    self.module.fail_json(msg="image %s is not one of this game's images: %s" % (p["docker_image"], ", ".join(images)))
                changed = True
                if not check:
                    self.call("setting the container image", c.update_game_server_docker_image, gs_id, p["docker_image"])
        return changed

    def run(self):
        p = self.p
        m = self.module
        c = self.client
        gs = resolve_game_server(self, p["id"] or p["name"], required=False)
        before = gs_view(gs)

        if p["state"] == "absent":
            if not gs:
                m.exit_json(changed=False, game_server={})
            if not m.check_mode:
                try:
                    c.delete_game_server(gs["id"])
                except NodeRingsError as e:
                    if not is_not_found(e):
                        self.fail("deleting game server %s" % gs.get("name"), e)
                if p["wait"]:
                    def gone():
                        try:
                            c.get_game_server(gs["id"])
                        except NodeRingsError as e:
                            if is_not_found(e):
                                return True, None
                            raise
                        return False, None
                    self.call("waiting for the deletion", self.waiter.wait, "game server to be deleted", gone)
            m.exit_json(changed=True, game_server={}, diff=dict(before=before, after={}))

        if not gs:
            if p["id"] and UUID_RE.match(p["id"]):
                m.fail_json(msg="game server %s does not exist" % p["id"])
            if not p["game"]:
                m.fail_json(msg="game is required to order game server %s" % p["name"])
            if not p["plan_id"] and not (p["plan_code"] and p["country"] and p["city"]):
                m.fail_json(msg="to order %s, set plan_id, or plan_code, country and city" % p["name"])
            plan_id, region_id = self.choose_plan()
            game = self.resolve_game(plan_id)
            after = dict(name=p["name"], plan_id=plan_id, region_id=region_id or "", game_name=game.get("name"))
            if m.check_mode:
                m.exit_json(changed=True, game_server=after, diff=dict(before={}, after=after))
            body = dict(planId=plan_id, templateId=game["id"], name=p["name"], idempotencyKey=new_uuid(), acceptEula=p["accept_eula"])
            if region_id:
                body["regionId"] = region_id
            if p["version"]:
                body["versionValue"] = p["version"]
            if p["environment"]:
                body["environment"] = dict((k, str(v)) for k, v in p["environment"].items())
            try:
                created = c.create_game_server(body)
            except NodeRingsError as e:
                if "new idempotency key" not in e.message.lower():
                    self.fail("ordering game server %s" % p["name"], e)
                body["idempotencyKey"] = new_uuid()
                created = self.call("ordering game server %s" % p["name"], c.create_game_server, body)
            gs_id = (created or {}).get("id")
            if not gs_id:
                m.fail_json(msg="the API accepted the order for %s but returned no ID; check the console before running again" % p["name"],
                            changed=True)
            if p["wait"] or p["docker_image"] or p["state"] in ("running", "offline", "restarted"):
                self.wait_installed(gs_id)
                if p["docker_image"]:
                    self.apply_settings(c.get_game_server(gs_id), False)
                if p["state"] in ("running", "offline", "restarted"):
                    self.power(gs_id, p["state"])
            after = gs_view(self.call("reading game server", c.get_game_server, gs_id))
            m.exit_json(changed=True, game_server=after, diff=dict(before={}, after=after))

        changed = False
        if p["game"]:
            game = self.resolve_game(gs["planId"])
            if game["id"] != gs.get("templateId"):
                if not p["allow_game_change"]:
                    m.warn("%s runs %s; set allow_game_change=true to switch to %s (this deletes all its files)"
                           % (gs.get("name"), gs.get("gameName"), game.get("name")))
                else:
                    changed = True
                    if not m.check_mode:
                        env = dict((k, str(v)) for k, v in p["environment"].items()) or None
                        self.call("changing the game", c.change_game_server_game, gs["id"], game["id"], env, p["accept_eula"])
                        if p["wait"]:
                            self.wait_installed(gs["id"])
        if gs.get("phase") != "GAME_SERVER_PHASE_READY" and not m.check_mode and (p["environment"] or p["docker_image"] or p["new_name"]):
            if not p["wait"]:
                m.fail_json(msg="game server %s is %s; settings can only change once it is ready" % (gs.get("name"), before.get("phase")))
            self.wait_installed(gs["id"])
        changed = self.apply_settings(gs, m.check_mode) or changed
        if p["state"] in ("running", "offline", "restarted"):
            if m.check_mode:
                state = (self.call("reading power state", c.get_game_server_resources, gs["id"]) or {}).get("state")
                changed = changed or p["state"] == "restarted" or state != p["state"]
            else:
                changed = self.power(gs["id"], p["state"]) or changed
        after = before
        if changed and not m.check_mode:
            after = gs_view(self.call("reading game server", c.get_game_server, gs["id"]))
        m.exit_json(changed=changed, game_server=after, diff=dict(before=before, after=after))


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str"),
        id=dict(type="str"),
        new_name=dict(type="str"),
        state=dict(type="str", default="present", choices=["present", "running", "offline", "restarted", "absent"]),
        plan_id=dict(type="str"),
        region_id=dict(type="str"),
        plan_code=dict(type="str"),
        country=dict(type="str"),
        city=dict(type="str"),
        billing_type=dict(type="str", choices=["usage", "subscription", "free"]),
        provider=dict(type="str"),
        provider_id=dict(type="str"),
        sort=dict(type="str", default="price", choices=["price", "rating"]),
        game=dict(type="str"),
        allow_game_change=dict(type="bool", default=False),
        accept_eula=dict(type="bool", default=False),
        version=dict(type="str"),
        environment=dict(type="dict", default={}),
        docker_image=dict(type="str"),
        wait=dict(type="bool", default=True),
        wait_timeout=dict(type="int", default=1800),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[("name", "id")],
        mutually_exclusive=[("plan_id", "plan_code"), ("provider", "provider_id")],
        required_together=[("plan_code", "country", "city")],
        supports_check_mode=True,
    )
    GameServer(module).run()


if __name__ == "__main__":
    main()
