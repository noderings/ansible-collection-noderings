#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: group
short_description: Manage IAM groups and their members in a NodeRings organization
version_added: 0.1.0
description:
  - Creates, updates and deletes groups, and keeps their members.
  - Give a group a role with M(noderings.cloud.role_assignment).
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
      - Name of the group. Unique within the organization.
    type: str
    required: true
  description:
    description:
      - Description of the group.
    type: str
  users:
    description:
      - Emails or IDs of the users in the group. Leave unset to not manage user members.
    type: list
    elements: str
  service_accounts:
    description:
      - Names or IDs of the service accounts in the group. Leave unset to not manage them.
    type: list
    elements: str
  purge_members:
    description:
      - Remove members that are not listed. With V(false), listed members are only added.
    type: bool
    default: true
  state:
    description:
      - Whether the group should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Operations team
  noderings.cloud.group:
    name: ops
    description: On-call engineers
    users: [alice@example.com, bob@example.com]
    service_accounts: [ci-deploy]
"""

RETURN = r"""
group:
  description: The group. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 3a2b1c0d-0000-0000-0000-000000000000
    name: ops
    description: On-call engineers
    users: [alice@example.com, bob@example.com]
    service_accounts: [ci-deploy]
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec


def resolve(nr, refs, items, key, what):
    out = {}
    for ref in refs or []:
        hit = next((i for i in items if i.get("id") == ref or (i.get(key) or "").lower() == ref.lower()), None)
        if not hit:
            nr.module.fail_json(msg="%s %s does not exist" % (what, ref))
        out[hit["id"]] = hit.get(key)
    return out


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        description=dict(type="str"),
        users=dict(type="list", elements="str"),
        service_accounts=dict(type="list", elements="str"),
        purge_members=dict(type="bool", default=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    users = nr.call("listing users", c.list_users)
    sas = nr.call("listing service accounts", c.list_service_accounts)

    def view(g):
        if not g:
            return {}
        gid = g.get("id")
        return dict(id=gid, name=g.get("name"), description=g.get("description") or "",
                    users=sorted(u.get("email") for u in users if gid in (u.get("groupIds") or [])),
                    service_accounts=sorted(s.get("name") for s in sas if gid in (s.get("groupIds") or [])),
                    role_ids=g.get("groupRoles") or [])

    groups = nr.call("listing groups", c.list_groups)
    current = next((g for g in groups if g.get("name") == p["name"]), None)
    before = view(current)

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, group={})
        if not module.check_mode:
            nr.call("deleting group %s" % p["name"], c.delete_group, current["id"])
        module.exit_json(changed=True, group={}, diff=dict(before=before, after={}))

    want_users = resolve(nr, p["users"], users, "email", "user") if p["users"] is not None else None
    want_sas = resolve(nr, p["service_accounts"], sas, "name", "service account") if p["service_accounts"] is not None else None
    changed = False
    if not current:
        changed = True
        if module.check_mode:
            after = dict(name=p["name"], description=p["description"] or "", users=sorted((want_users or {}).values()),
                         service_accounts=sorted((want_sas or {}).values()), role_ids=[])
            module.exit_json(changed=True, group=after, diff=dict(before={}, after=after))
        current = nr.call("creating group %s" % p["name"], c.create_group, p["name"], p["description"])
    elif p["description"] is not None and p["description"] != (current.get("description") or ""):
        changed = True
        if not module.check_mode:
            nr.call("updating group %s" % p["name"], c.update_group, current["id"], p["name"], p["description"])
    gid = current["id"]
    have_users = set(u["id"] for u in users if gid in (u.get("groupIds") or []))
    have_sas = set(s["id"] for s in sas if gid in (s.get("groupIds") or []))
    ops = []
    if want_users is not None:
        add = sorted(set(want_users) - have_users)
        rem = sorted(have_users - set(want_users)) if p["purge_members"] else []
        if add:
            ops.append(("adding users", c.add_users_to_group, add))
        if rem:
            ops.append(("removing users", c.remove_users_from_group, rem))
    if want_sas is not None:
        add = sorted(set(want_sas) - have_sas)
        rem = sorted(have_sas - set(want_sas)) if p["purge_members"] else []
        if add:
            ops.append(("adding service accounts", c.add_service_accounts_to_group, add))
        if rem:
            ops.append(("removing service accounts", c.remove_service_accounts_from_group, rem))
    if ops:
        changed = True
        if not module.check_mode:
            for what, fn, ids in ops:
                nr.call("%s to/from %s" % (what, p["name"]), fn, gid, ids)
    if not changed:
        module.exit_json(changed=False, group=before)
    if module.check_mode:
        after = dict(before)
        if p["description"] is not None:
            after["description"] = p["description"]
        if want_users is not None:
            after["users"] = sorted(set(want_users.values()) | (set() if p["purge_members"] else set(before.get("users") or [])))
        if want_sas is not None:
            after["service_accounts"] = sorted(set(want_sas.values()) | (set() if p["purge_members"] else set(before.get("service_accounts") or [])))
        module.exit_json(changed=True, group=after, diff=dict(before=before, after=after))
    users = nr.call("listing users", c.list_users)
    sas = nr.call("listing service accounts", c.list_service_accounts)
    g = next((x for x in nr.call("listing groups", c.list_groups) if x.get("id") == gid), current)
    after = view(g)
    module.exit_json(changed=True, group=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
