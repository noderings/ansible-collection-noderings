#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: role
short_description: Manage custom IAM roles in a NodeRings organization
version_added: 0.1.0
description:
  - Creates, updates and deletes custom roles. A role is a set of API permissions.
  - Built-in roles (Owner, Administrator, Operator, Billing, Viewer) cannot be changed or deleted.
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
  name:
    description:
      - Name of the role. Unique within the organization.
    type: str
    required: true
  description:
    description:
      - Description of the role.
    type: str
  permissions:
    description:
      - Permissions, by method name such as C(ListVirtualMachines) or by ID. See M(noderings.cloud.iam_info).
      - Leave unset to not manage permissions.
    type: list
    elements: str
  purge_permissions:
    description:
      - Remove permissions that are not in O(permissions). With V(false), O(permissions) are only added.
    type: bool
    default: true
  state:
    description:
      - Whether the role should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Read-only access to servers and DNS
  noderings.cloud.role:
    name: server-viewer
    description: Can see servers and DNS
    permissions:
      - ListVirtualMachines
      - GetVirtualMachine
      - ListDnsZones
      - ListDnsRecords
"""

RETURN = r"""
role:
  description: The role. C(permissions) are method names. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 4c3b2a19-0000-0000-0000-000000000000
    name: server-viewer
    description: Can see servers and DNS
    is_builtin: false
    permissions: [GetVirtualMachine, ListDnsRecords, ListDnsZones, ListVirtualMachines]
    permission_ids: [043f4a01-0000-0000-0000-000000000000]
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    resolve_permissions,
)


def view(r, by_id):
    if not r:
        return {}
    ids = sorted(r.get("permissions") or [])
    return dict(id=r.get("id"), name=r.get("name"), description=r.get("description") or "", is_builtin=bool(r.get("isBuiltin")),
                permissions=sorted(set((by_id.get(i) or {}).get("methodName") or i for i in ids)), permission_ids=ids)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        description=dict(type="str"),
        permissions=dict(type="list", elements="str"),
        purge_permissions=dict(type="bool", default=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    want_ids, by_id = resolve_permissions(nr, p["permissions"] or [])
    roles = nr.call("listing roles", c.list_roles)
    current = next((r for r in roles if r.get("name") == p["name"]), None)
    before = view(current, by_id)
    if current and current.get("isBuiltin"):
        module.fail_json(msg="%s is a built-in role and cannot be changed or deleted" % p["name"])

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, role={})
        if not module.check_mode:
            nr.call("deleting role %s" % p["name"], c.delete_role, current["id"])
        module.exit_json(changed=True, role={}, diff=dict(before=before, after={}))

    if not current:
        after = dict(name=p["name"], description=p["description"] or "", is_builtin=False,
                     permissions=sorted(set(by_id[i].get("methodName") for i in want_ids)), permission_ids=want_ids)
        if not module.check_mode:
            created = nr.call("creating role %s" % p["name"], c.create_role, p["name"], p["description"], want_ids)
            roles = nr.call("listing roles", c.list_roles)
            after = view(next((r for r in roles if r.get("id") == (created or {}).get("id")), created), by_id)
        module.exit_json(changed=True, role=after, diff=dict(before={}, after=after))

    changed = False
    have = set(current.get("permissions") or [])
    add = sorted(set(want_ids) - have) if p["permissions"] is not None else []
    remove = sorted(have - set(want_ids)) if (p["permissions"] is not None and p["purge_permissions"]) else []
    desc_changed = p["description"] is not None and p["description"] != (current.get("description") or "")
    if desc_changed:
        changed = True
        if not module.check_mode:
            nr.call("updating role %s" % p["name"], c.update_role, current["id"], p["name"], p["description"])
    if add:
        changed = True
        if not module.check_mode:
            nr.call("adding permissions to %s" % p["name"], c.assign_permissions, current["id"], add)
    if remove:
        changed = True
        if not module.check_mode:
            nr.call("removing permissions from %s" % p["name"], c.remove_permissions, current["id"], remove)
    if not changed:
        module.exit_json(changed=False, role=before)
    if module.check_mode:
        ids = sorted((have | set(add)) - set(remove))
        after = dict(before, description=p["description"] if desc_changed else before["description"], permission_ids=ids,
                     permissions=sorted(set((by_id.get(i) or {}).get("methodName") or i for i in ids)))
    else:
        roles = nr.call("listing roles", c.list_roles)
        after = view(next((r for r in roles if r.get("id") == current["id"]), None), by_id)
    module.exit_json(changed=True, role=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
