#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: ssh_key
short_description: Manage SSH keys in a NodeRings organization
version_added: 0.1.0
description:
  - Adds or removes an SSH public key that can be installed on new virtual machines.
  - Keys are matched by O(name). The API cannot change a key in place, so a different O(public_key)
    under the same name replaces the key (it gets a new ID).
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
      - Name of the key. Unique within the organization.
    type: str
    required: true
  public_key:
    description:
      - The public key, for example the contents of C(~/.ssh/id_ed25519.pub).
      - Required when O(state=present). Surrounding whitespace and the trailing comment are ignored when comparing.
    type: str
  state:
    description:
      - Whether the key should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Upload my laptop key
  noderings.cloud.ssh_key:
    name: laptop
    public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/id_ed25519.pub') }}"
  register: key

- name: Remove an old key
  noderings.cloud.ssh_key:
    name: old-laptop
    state: absent
"""

RETURN = r"""
ssh_key:
  description: The key. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 8b0f3c1e-1d2a-4f6b-9c3e-2a1b0c9d8e7f
    name: laptop
    key_type: ssh-ed25519
    fingerprint: SHA256:abc...
    public_key: ssh-ed25519 AAAA... me@laptop
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    snake,
)


def key_material(public_key):
    """Key type and base64 body, ignoring the comment and whitespace."""
    parts = (public_key or "").split()
    return " ".join(parts[:2])


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        public_key=dict(type="str", no_log=False),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["public_key"])],
        supports_check_mode=True,
    )
    nr = NodeRingsModule(module)
    name = module.params["name"]
    keys = nr.call("listing SSH keys", nr.client.list_ssh_keys)
    current = next((k for k in keys if k.get("name") == name), None)
    before = snake(current) if current else {}

    if module.params["state"] == "absent":
        if current:
            if not module.check_mode:
                nr.call("deleting SSH key %s" % name, nr.client.delete_ssh_key, current["id"])
            module.exit_json(changed=True, ssh_key={}, diff=dict(before=before, after={}))
        module.exit_json(changed=False, ssh_key={})

    wanted = module.params["public_key"].strip()
    if current and key_material(current.get("publicKey")) == key_material(wanted):
        module.exit_json(changed=False, ssh_key=before)

    after = dict(before, name=name, public_key=wanted)
    if module.check_mode:
        module.exit_json(changed=True, ssh_key=after, diff=dict(before=before, after=after))
    if current:
        nr.call("replacing SSH key %s" % name, nr.client.delete_ssh_key, current["id"])
    created = nr.call("creating SSH key %s" % name, nr.client.create_ssh_key, name, wanted)
    result = snake(created or {})
    module.exit_json(changed=True, ssh_key=result, diff=dict(before=before, after=result))


if __name__ == "__main__":
    main()
