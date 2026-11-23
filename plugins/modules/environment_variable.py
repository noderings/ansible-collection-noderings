#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: environment_variable
short_description: Manage environment variables in a NodeRings organization
version_added: 0.1.0
description:
  - Creates, updates and deletes organization environment variables, which game servers and instant apps can use.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: partial
    details: Values are never shown in the diff.
options:
  key:
    description:
      - Name of the environment variable, for example C(DATABASE_URL). Unique within the organization.
      - Keys are case-insensitive; the API may store them in lower case.
    type: str
    required: true
  value:
    description:
      - The value. Required when O(state=present).
    type: str
  state:
    description:
      - Whether the environment variable should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Store an API key
  noderings.cloud.environment_variable:
    key: STRIPE_API_KEY
    value: "{{ vault_stripe_key }}"
"""

RETURN = r"""
environment_variable:
  description: The environment variable without its value. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 0a1b2c3d-0000-0000-0000-000000000000
    key: STRIPE_API_KEY
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec


def view(x):
    if not x:
        return {}
    return dict(id=x.get("id"), key=x.get("key"), status=x.get("status"))


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        key=dict(type="str", required=True, no_log=False),
        value=dict(type="str", no_log=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, required_if=[("state", "present", ["value"])], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    items = nr.call("listing environment variables", c.list_environment_variables)
    current = next((x for x in items if (x.get("key") or "").lower() == p["key"].lower()), None)
    before = view(current)
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, environment_variable={})
        if not module.check_mode:
            nr.call("deleting environment variable %s" % p["key"], c.delete_environment_variable, current["id"])
        module.exit_json(changed=True, environment_variable={}, diff=dict(before=before, after={}))
    if not current:
        if module.check_mode:
            module.exit_json(changed=True, environment_variable=dict(key=p["key"]), diff=dict(before={}, after=dict(key=p["key"])))
        created = nr.call("creating environment variable %s" % p["key"], c.create_environment_variable, p["key"], p["value"])
        module.exit_json(changed=True, environment_variable=view(created), diff=dict(before={}, after=view(created)))
    if current.get("value") == p["value"]:
        module.exit_json(changed=False, environment_variable=before)
    if not module.check_mode:
        nr.call("updating environment variable %s" % p["key"], c.update_environment_variable, current["id"], p["value"])
    module.exit_json(changed=True, environment_variable=before,
                     diff=dict(before=dict(key=p["key"], value="<hidden>"), after=dict(key=p["key"], value="<changed>")))


if __name__ == "__main__":
    main()
