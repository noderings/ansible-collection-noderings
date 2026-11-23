#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: game_server_game_info
short_description: List the games a NodeRings game-server plan can run
version_added: 0.1.0
description:
  - Lists the games (and their startup variables) that can be installed on a game-server plan.
    Games are specific to the plan's provider.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: none
options:
  plan_id:
    description:
      - The game-server plan, for example RV(noderings.cloud.marketplace_offer_info#module:offer.plan_id).
    type: str
    required: true
  name:
    description:
      - Only the game with this name (case-insensitive).
    type: str
"""

EXAMPLES = r"""
- name: Find an offer, then its games
  noderings.cloud.marketplace_offer_info:
    plan_code: SC-GS-4C-8G-50
    country: Germany
    city: Frankfurt
    asset_type: game_server
  register: found

- noderings.cloud.game_server_game_info:
    plan_id: "{{ found.offer.plan_id }}"
  register: games
"""

RETURN = r"""
games:
  description: The games. C(eula) is true when O(noderings.cloud.game_server#module:accept_eula) is required.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(plan_id=dict(type="str", required=True), name=dict(type="str"))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    games = nr.call("listing games", nr.client.list_order_games, module.params["plan_id"])
    name = (module.params["name"] or "").lower()
    out = []
    for g in games:
        if name and (g.get("name") or "").lower() != name:
            continue
        item = snake(g)
        item["eula"] = bool(g.get("eula"))
        out.append(item)
    module.exit_json(changed=False, games=out)


if __name__ == "__main__":
    main()
