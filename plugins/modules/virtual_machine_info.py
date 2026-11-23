#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: virtual_machine_info
short_description: List NodeRings virtual machines
version_added: 0.1.0
description:
  - Lists the organization's virtual machines, optionally filtered, with their snapshots and backups on request.
  - To use your VMs as Ansible hosts, see the P(noderings.cloud.noderings#inventory) inventory plugin.
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
  id:
    description:
      - Only return the VM with this ID.
    type: str
  hostname:
    description:
      - Only return VMs with this hostname.
    type: str
  tags:
    description:
      - Only return VMs that have all of these tags.
    type: list
    elements: str
    default: []
  include_snapshots:
    description:
      - Also return each VM's snapshots (one extra request per VM).
    type: bool
    default: false
  include_backups:
    description:
      - Also return each VM's backups (one extra request per VM).
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: All production servers
  noderings.cloud.virtual_machine_info:
    tags: [prod]
  register: prod

- name: Their addresses
  ansible.builtin.debug:
    msg: "{{ prod.virtual_machines | map(attribute='ipv4') | list }}"
"""

RETURN = r"""
virtual_machines:
  description: The matching VMs. See the return value of M(noderings.cloud.virtual_machine) for the fields.
  returned: always
  type: list
  elements: dict
tags:
  description: Every tag used on the organization's VMs.
  returned: always
  type: list
  elements: str
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import NONCE_TAG_PREFIX, vm_view
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        id=dict(type="str"),
        hostname=dict(type="str"),
        tags=dict(type="list", elements="str", default=[]),
        include_snapshots=dict(type="bool", default=False),
        include_backups=dict(type="bool", default=False),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    vms = nr.call("listing virtual machines", c.list_virtual_machines)
    want_tags = set(p["tags"])
    out = []
    for vm in vms:
        if p["id"] and vm.get("id") != p["id"]:
            continue
        if p["hostname"] and vm.get("hostname") != p["hostname"]:
            continue
        if not want_tags.issubset(set(vm.get("tags") or [])):
            continue
        item = vm_view(vm)
        if p["include_snapshots"]:
            item["snapshots"] = snake(nr.call("listing snapshots of %s" % vm.get("hostname"), c.list_snapshots, vm["id"]))
        if p["include_backups"]:
            item["backups"] = snake(nr.call("listing backups of %s" % vm.get("hostname"), c.list_backups, vm["id"]))
        out.append(item)
    tags = [t for t in nr.call("listing tags", c.list_vm_tags) if not t.startswith(NONCE_TAG_PREFIX)]
    module.exit_json(changed=False, virtual_machines=out, tags=sorted(tags))


if __name__ == "__main__":
    main()
