#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: game_server_backup
short_description: Take, lock and delete backups of a NodeRings game server
version_added: 0.1.0
description:
  - Takes a backup of a game server's files, or deletes one. Backups are matched by O(name).
  - A locked backup cannot be deleted until it is unlocked. The plan limits how many backups a server can have.
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
    support: none
options:
  game_server:
    description:
      - Name or ID of the game server.
    type: str
    required: true
  name:
    description:
      - Name of the backup.
    type: str
    required: true
  locked:
    description:
      - Lock or unlock the backup. Leave unset to not manage the lock.
    type: bool
  state:
    description:
      - Whether the backup should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Back up before an update
  noderings.cloud.game_server_backup:
    game_server: survival
    name: before-1.21
    locked: true
"""

RETURN = r"""
backup:
  description: The backup. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    uuid: 0f1e2d3c-0000-0000-0000-000000000000
    name: before-1.21
    is_successful: true
    is_locked: true
    bytes: "104857600"
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.gameserver import resolve_game_server
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, Waiter, noderings_argument_spec, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        game_server=dict(type="str", required=True),
        name=dict(type="str", required=True),
        locked=dict(type="bool"),
        state=dict(type="str", default="present", choices=["present", "absent"]),
        wait=dict(type="bool", default=True),
        wait_timeout=dict(type="int", default=1800),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    gid = resolve_game_server(nr, p["game_server"])["id"]

    def find():
        return next((b for b in nr.call("listing backups", c.list_game_server_backups, gid) if b.get("name") == p["name"]), None)

    current = find()
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, backup={})
        if current.get("isLocked") and p["locked"] is not False:
            module.fail_json(msg="backup %s is locked; set locked=false to unlock and delete it" % p["name"])
        if not module.check_mode:
            if current.get("isLocked"):
                nr.call("unlocking backup", c.toggle_game_server_backup_lock, gid, current["uuid"])
            nr.call("deleting backup", c.delete_game_server_backup, gid, current["uuid"])
        module.exit_json(changed=True, backup={})
    changed = False
    if not current:
        changed = True
        if module.check_mode:
            module.exit_json(changed=True, backup=dict(name=p["name"], is_locked=bool(p["locked"])))
        nr.call("taking a backup", c.create_game_server_backup, gid, p["name"])
        if p["wait"] or p["locked"] is not None:
            def done():
                b = find()
                return bool(b and b.get("completedAt")), b

            current = nr.call("waiting for the backup", Waiter(p["wait_timeout"], interval=5).wait, "the backup to complete", done)
            if not current.get("isSuccessful"):
                module.fail_json(msg="backup %s did not succeed" % p["name"], changed=True, backup=snake(current))
        else:
            current = find() or dict(name=p["name"])
    if p["locked"] is not None and bool(current.get("isLocked")) != p["locked"]:
        changed = True
        if not module.check_mode:
            nr.call("changing the backup lock", c.toggle_game_server_backup_lock, gid, current["uuid"])
            current = find() or current
        else:
            current = dict(current, isLocked=p["locked"])
    module.exit_json(changed=changed, backup=snake(current))


if __name__ == "__main__":
    main()
