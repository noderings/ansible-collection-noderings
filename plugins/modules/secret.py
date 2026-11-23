#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: secret
short_description: Manage secrets in a NodeRings organization
version_added: 0.1.0
description:
  - Creates, updates and deletes organization secrets, which game servers and instant apps can use.
  - Secret values are write-only, the API never returns them. Use O(update_value) to control when a value is rewritten.
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
      - Name of the secret, for example C(DATABASE_URL). Unique within the organization.
      - Keys are case-insensitive; the API may store them in lower case.
    type: str
    required: true
  value:
    description:
      - The value. Required when O(state=present). Never returned or logged.
    type: str
  update_value:
    description:
      - V(always) rewrites the value on every run (reported as changed), V(on_create) only sets it when the secret is created.
    type: str
    choices: [always, on_create]
    default: always
  state:
    description:
      - Whether the secret should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Store an API key
  noderings.cloud.secret:
    key: STRIPE_API_KEY
    value: "{{ vault_stripe_key }}"
"""

RETURN = r"""
secret:
  description: The secret without its value. Empty after O(state=absent).
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
        update_value=dict(type="str", default="always", choices=["always", "on_create"]),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, required_if=[("state", "present", ["value"])], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    items = nr.call("listing secrets", c.list_secrets)
    current = next((x for x in items if (x.get("key") or "").lower() == p["key"].lower()), None)
    before = view(current)
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, secret={})
        if not module.check_mode:
            nr.call("deleting secret %s" % p["key"], c.delete_secret, current["id"])
        module.exit_json(changed=True, secret={}, diff=dict(before=before, after={}))
    if not current:
        if module.check_mode:
            module.exit_json(changed=True, secret=dict(key=p["key"]), diff=dict(before={}, after=dict(key=p["key"])))
        created = nr.call("creating secret %s" % p["key"], c.create_secret, p["key"], p["value"])
        module.exit_json(changed=True, secret=view(created), diff=dict(before={}, after=view(created)))
    if p["update_value"] == "on_create":
        module.exit_json(changed=False, secret=before)
    if not module.check_mode:
        nr.call("updating secret %s" % p["key"], c.update_secret, current["id"], p["value"])
    module.exit_json(changed=True, secret=before,
                     diff=dict(before=dict(key=p["key"], value="<hidden>"), after=dict(key=p["key"], value="<changed>")))


if __name__ == "__main__":
    main()
