#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: game_server_database
short_description: Manage databases of a NodeRings game server
version_added: 0.1.0
description:
  - Creates or deletes a MySQL database for a game server (for plugins that need one), and rotates its password.
  - The password is only returned when the database is created or its password is rotated.
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
  game_server:
    description:
      - Name or ID of the game server.
    type: str
    required: true
  name:
    description:
      - Database name. The platform may add a prefix; the module matches names with or without it.
    type: str
    required: true
  remote:
    description:
      - Hosts allowed to connect, for example C(%) for anywhere or an IP address.
    type: str
    default: "%"
  rotate_password:
    description:
      - Set a new random password (reported as changed).
    type: bool
    default: false
  state:
    description:
      - Whether the database should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Database for a plugin
  noderings.cloud.game_server_database:
    game_server: survival
    name: luckperms
  register: db

- name: Use it
  ansible.builtin.debug:
    msg: "{{ db.database.host }}:{{ db.database.port }} as {{ db.database.username }}"
"""

RETURN = r"""
database:
  description: The database. C(password) is only set right after creation or rotation. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: "7"
    name: s12_luckperms
    username: u12_abc
    host: 203.0.113.30
    port: 3306
    connections_from: "%"
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.gameserver import resolve_game_server
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake


def view(d, keep_password=False):
    out = snake(d or {})
    if not keep_password:
        out.pop("password", None)
        out.pop("jdbc", None)
    return out


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        game_server=dict(type="str", required=True),
        name=dict(type="str", required=True),
        remote=dict(type="str", default="%"),
        rotate_password=dict(type="bool", default=False, no_log=False),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    gid = resolve_game_server(nr, p["game_server"])["id"]
    dbs = nr.call("listing databases", c.list_game_server_databases, gid)
    current = next((d for d in dbs if d.get("name") == p["name"] or (d.get("name") or "").endswith("_" + p["name"])), None)
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, database={})
        if not module.check_mode:
            nr.call("deleting database", c.delete_game_server_database, gid, current["id"])
        module.exit_json(changed=True, database={})
    if not current:
        if module.check_mode:
            module.exit_json(changed=True, database=dict(name=p["name"], connections_from=p["remote"]))
        created = nr.call("creating database", c.create_game_server_database, gid, p["name"], p["remote"])
        module.exit_json(changed=True, database=view(created, keep_password=True))
    if p["rotate_password"]:
        if module.check_mode:
            module.exit_json(changed=True, database=view(current))
        rotated = nr.call("rotating the password", c.rotate_game_server_database_password, gid, current["id"])
        module.exit_json(changed=True, database=view(dict(current, **(rotated or {})), keep_password=True))
    module.exit_json(changed=False, database=view(current))


if __name__ == "__main__":
    main()
