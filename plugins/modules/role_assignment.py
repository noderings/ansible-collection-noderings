#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: role_assignment
short_description: Give a NodeRings user, group or service account its role
version_added: 0.1.0
description:
  - Sets the direct role of a user, group or service account.
  - Each principal has exactly one direct role, so this replaces any role it had.
    Be careful when changing the role of the service account that runs the playbook.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
options:
  user:
    description:
      - Email or ID of the user. Exactly one of O(user), O(group) and O(service_account) is required.
    type: str
  group:
    description:
      - Name or ID of the group.
    type: str
  service_account:
    description:
      - Name or ID of the service account.
    type: str
  role:
    description:
      - Name or ID of the role, built-in (for example C(Viewer)) or custom.
    type: str
    required: true
"""

EXAMPLES = r"""
- name: Everyone in ops gets the Operator role
  noderings.cloud.role_assignment:
    group: ops
    role: Operator

- name: Read-only auditor
  noderings.cloud.role_assignment:
    user: carol@example.com
    role: Viewer
"""

RETURN = r"""
assignment:
  description: The principal and its role.
  returned: always
  type: dict
  sample:
    principal_type: group
    principal_id: 3a2b1c0d-0000-0000-0000-000000000000
    principal_name: ops
    role_id: f2e9ea36-0000-0000-0000-000000000000
    role_name: Operator
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    resolve_role,
)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(user=dict(type="str"), group=dict(type="str"), service_account=dict(type="str"), role=dict(type="str", required=True))
    module = AnsibleModule(argument_spec=argument_spec, required_one_of=[("user", "group", "service_account")],
                           mutually_exclusive=[("user", "group", "service_account")], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    role = resolve_role(nr, p["role"])
    if p["user"]:
        kind, ref = "user", p["user"]
        items = nr.call("listing users", c.list_users)
        principal = next((u for u in items if u.get("id") == ref or (u.get("email") or "").lower() == ref.lower()), None)
        have = principal.get("userRoles") if principal else None
        name = principal.get("email") if principal else None
    elif p["group"]:
        kind, ref = "group", p["group"]
        items = nr.call("listing groups", c.list_groups)
        principal = next((g for g in items if g.get("id") == ref or g.get("name") == ref), None)
        have = principal.get("groupRoles") if principal else None
        name = principal.get("name") if principal else None
    else:
        kind, ref = "service_account", p["service_account"]
        items = nr.call("listing service accounts", c.list_service_accounts)
        principal = next((s for s in items if s.get("id") == ref or s.get("name") == ref), None)
        have = principal.get("roleIds") if principal else None
        name = principal.get("name") if principal else None
    if not principal:
        module.fail_json(msg="%s %s does not exist" % (kind.replace("_", " "), ref))
    have = list(have or [])
    result = dict(principal_type=kind, principal_id=principal["id"], principal_name=name, role_id=role["id"], role_name=role.get("name"))
    if have == [role["id"]]:
        module.exit_json(changed=False, assignment=result)
    if not module.check_mode:
        nr.call("assigning role %s to %s" % (role.get("name"), name), c.replace_role, kind, principal["id"], role["id"])
    module.exit_json(changed=True, assignment=result, diff=dict(before=dict(role_ids=have), after=dict(role_ids=[role["id"]])))


if __name__ == "__main__":
    main()
