#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: iam_info
short_description: List users, groups, roles, service accounts and permissions of a NodeRings organization
version_added: 0.1.0
description:
  - Returns the organization's identity and access setup, for audits or to look up IDs.
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
  gather_subset:
    description:
      - Which lists to return.
    type: list
    elements: str
    choices: [users, groups, roles, service_accounts, permissions, secrets, environment_variables]
    default: [users, groups, roles, service_accounts]
  permission_filter:
    description:
      - With C(permissions) in O(gather_subset), only permissions whose method name contains this text.
    type: str
"""

EXAMPLES = r"""
- name: Who has access?
  noderings.cloud.iam_info:
  register: iam

- name: Permission names for a custom role
  noderings.cloud.iam_info:
    gather_subset: [permissions]
    permission_filter: VirtualMachine
  register: perms
"""

RETURN = r"""
users:
  description: Members of the organization.
  returned: when C(users) is in O(gather_subset)
  type: list
  elements: dict
groups:
  description: Groups.
  returned: when C(groups) is in O(gather_subset)
  type: list
  elements: dict
roles:
  description: Built-in and custom roles. C(permissions) holds permission IDs.
  returned: when C(roles) is in O(gather_subset)
  type: list
  elements: dict
service_accounts:
  description: Service accounts.
  returned: when C(service_accounts) is in O(gather_subset)
  type: list
  elements: dict
permissions:
  description: API permissions that can be put in a role.
  returned: when C(permissions) is in O(gather_subset)
  type: list
  elements: dict
secrets:
  description: Organization secrets, without their values.
  returned: when C(secrets) is in O(gather_subset)
  type: list
  elements: dict
environment_variables:
  description: Organization environment variables, with their values.
  returned: when C(environment_variables) is in O(gather_subset)
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, pick, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        gather_subset=dict(type="list", elements="str", default=["users", "groups", "roles", "service_accounts"],
                           choices=["users", "groups", "roles", "service_accounts", "permissions", "secrets", "environment_variables"]),
        permission_filter=dict(type="str"),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    want = set(module.params["gather_subset"])
    out = dict(changed=False)
    if "users" in want:
        out["users"] = [pick(u, "id", "email", "firstName", "lastName", "isVerified", "userRoles", "groupIds", "status")
                        for u in nr.call("listing users", c.list_users)]
    if "groups" in want:
        out["groups"] = [pick(g, "id", "name", "description", "groupRoles", "status") for g in nr.call("listing groups", c.list_groups)]
    if "roles" in want:
        out["roles"] = [pick(r, "id", "name", "description", "isBuiltin", "permissions", "groupIds") for r in nr.call("listing roles", c.list_roles)]
    if "service_accounts" in want:
        out["service_accounts"] = [pick(s, "id", "name", "description", "isActive", "roleIds", "groupIds", "allowedIps")
                                   for s in nr.call("listing service accounts", c.list_service_accounts)]
    if "permissions" in want:
        perms = nr.call("listing permissions", c.list_permissions)
        f = (module.params["permission_filter"] or "").lower()
        out["permissions"] = [snake(x) for x in perms if f in (x.get("methodName") or "").lower()]
    if "secrets" in want:
        out["secrets"] = [pick(s, "id", "key", "status") for s in nr.call("listing secrets", c.list_secrets)]
    if "environment_variables" in want:
        out["environment_variables"] = [pick(e, "id", "key", "value", "status") for e in nr.call("listing environment variables", c.list_environment_variables)]
    module.exit_json(**out)


if __name__ == "__main__":
    main()
