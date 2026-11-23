#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: ssh_key_info
short_description: List SSH keys in a NodeRings organization
version_added: 0.1.0
description:
  - Lists the organization's SSH keys, optionally filtered by name or ID.
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
      - Only return the key with this name.
    type: str
  id:
    description:
      - Only return the key with this ID.
    type: str
"""

EXAMPLES = r"""
- name: Find a key's ID for a new server
  noderings.cloud.ssh_key_info:
    name: laptop
  register: keys

- name: Use it
  ansible.builtin.debug:
    msg: "{{ keys.ssh_keys[0].id }}"
"""

RETURN = r"""
ssh_keys:
  description: The matching keys.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    snake,
)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(name=dict(type="str"), id=dict(type="str"))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    keys = nr.call("listing SSH keys", nr.client.list_ssh_keys)
    name, key_id = module.params["name"], module.params["id"]
    keys = [k for k in keys if (not name or k.get("name") == name) and (not key_id or k.get("id") == key_id)]
    module.exit_json(changed=False, ssh_keys=snake(keys))


if __name__ == "__main__":
    main()
