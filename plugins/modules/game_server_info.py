#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: game_server_info
short_description: List NodeRings game servers
version_added: 0.1.0
description:
  - Lists the organization's game servers. With O(name) or O(id), also returns live resources,
    startup settings, extra ports, databases and backups of that server.
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
  name:
    description:
      - Only the server with this name.
    type: str
  id:
    description:
      - Only the server with this ID.
    type: str
"""

EXAMPLES = r"""
- name: All game servers
  noderings.cloud.game_server_info:
  register: servers

- name: Details of one
  noderings.cloud.game_server_info:
    name: survival
  register: mc
"""

RETURN = r"""
game_servers:
  description: The servers. See M(noderings.cloud.game_server) for the fields.
  returned: always
  type: list
  elements: dict
details:
  description: Live resources, startup settings, allocations, databases and backups of the one matching server.
  returned: when O(name) or O(id) matches one server
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.gameserver import gs_view
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(name=dict(type="str"), id=dict(type="str"))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    servers = [g for g in nr.call("listing game servers", c.list_game_servers)
               if (not p["name"] or g.get("name") == p["name"]) and (not p["id"] or g.get("id") == p["id"])]
    result = dict(changed=False, game_servers=[gs_view(g) for g in servers])
    if (p["name"] or p["id"]) and len(servers) == 1:
        gid = servers[0]["id"]
        startup = nr.call("reading startup settings", c.get_game_server_startup, gid) or {}
        for v in startup.get("variables") or []:
            v.pop("rules", None)
        result["details"] = dict(
            resources=snake(nr.call("reading resources", c.get_game_server_resources, gid)),
            startup=snake(startup),
            allocations=snake(nr.call("listing allocations", c.get, c.gs_path(gid, "/allocations")).get("allocations") or []),
            databases=[dict((k, v) for k, v in snake(d).items() if k != "password")
                       for d in nr.call("listing databases", c.list_game_server_databases, gid)],
            backups=snake(nr.call("listing backups", c.list_game_server_backups, gid)),
        )
    module.exit_json(**result)


if __name__ == "__main__":
    main()
