#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: virtual_machine_additional_ip
short_description: Add or remove additional IPv4 addresses on a NodeRings virtual machine
version_added: 0.1.0
description:
  - Makes a virtual machine have O(count) additional IPv4 addresses, or releases one address.
  - B(Billing.) On usage-billed VMs each address is charged per hour; on subscription VMs it is a monthly
    add-on charged pro rata now. Released addresses are cancelled immediately.
  - The new address is assigned by the provider. Configure it inside the guest yourself unless the provider does it.
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
  virtual_machine:
    description:
      - Hostname or ID of the VM.
    type: str
    required: true
    aliases: [vm]
  count:
    description:
      - How many additional IPv4 addresses the VM should have. Used with O(state=present).
      - When there are more, the most recently listed ones are released.
    type: int
  ip_address:
    description:
      - With O(state=absent), the address to release.
    type: str
  state:
    description:
      - V(present) adds or releases addresses until there are O(count).
      - V(absent) releases O(ip_address), or all additional addresses when O(ip_address) is not set.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Give the mail server a second address
  noderings.cloud.virtual_machine_additional_ip:
    vm: mail-1
    count: 1
  register: ips

- name: Release one address
  noderings.cloud.virtual_machine_additional_ip:
    vm: mail-1
    ip_address: 203.0.113.77
    state: absent
"""

RETURN = r"""
additional_ips:
  description: The VM's additional addresses afterwards.
  returned: always
  type: list
  elements: dict
  sample:
    - ip_address: 203.0.113.77
      gateway: 203.0.113.1
      prefix_length: 24
added:
  description: Addresses added by this run.
  returned: always
  type: list
  elements: str
removed:
  description: Addresses released by this run.
  returned: always
  type: list
  elements: str
billing_message:
  description: What the API said about the charge for the last added address.
  returned: when an address was added
  type: str
"""

import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import resolve_vm
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    Waiter,
    int_or_zero,
    noderings_argument_spec,
)

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def ips(vm):
    return [dict(ip_address=a.get("ipAddress"), gateway=a.get("gateway"), prefix_length=int_or_zero(a.get("prefixLength")))
            for a in vm.get("additionalIpv4") or []]


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        virtual_machine=dict(type="str", required=True, aliases=["vm"]),
        count=dict(type="int"),
        ip_address=dict(type="str"),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["count"])],
        mutually_exclusive=[("count", "ip_address")],
        supports_check_mode=True,
    )
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    ref = p["virtual_machine"]
    is_id = bool(UUID_RE.match(ref))
    vm = resolve_vm(nr, ref if is_id else None, None if is_id else ref)
    vm_id = vm["id"]
    have = ips(vm)
    have_addrs = [a["ip_address"] for a in have]
    waiter = Waiter(600)

    if p["state"] == "absent":
        drop = [p["ip_address"]] if p["ip_address"] else list(have_addrs)
        drop = [a for a in drop if a in have_addrs]
        target = len(have_addrs) - len(drop)
        add_n = 0
    else:
        if p["count"] < 0:
            module.fail_json(msg="count must be 0 or more")
        target = p["count"]
        add_n = max(0, target - len(have_addrs))
        drop = list(reversed(have_addrs))[: max(0, len(have_addrs) - target)]

    if not add_n and not drop:
        module.exit_json(changed=False, additional_ips=have, added=[], removed=[])
    if module.check_mode:
        after = [a for a in have if a["ip_address"] not in drop] + [dict(ip_address="(new)")] * add_n
        module.exit_json(changed=True, additional_ips=after, added=["(new)"] * add_n, removed=drop,
                         diff=dict(before=dict(additional_ips=have_addrs), after=dict(additional_ips=[a["ip_address"] for a in after])))

    removed, added, billing = [], [], None
    for addr in drop:
        nr.call("releasing %s" % addr, waiter.retry_busy,
                lambda a=addr: c.request("POST", c.vm_path(vm_id) + ":disable-additional-ip", body={"ipAddress": a, "cancelImmediately": True}))
        removed.append(addr)
    for dummy in range(add_n):
        known = set(a["ip_address"] for a in ips(c.get_virtual_machine(vm_id)))
        # Never retried blindly: each call orders one address.
        res = nr.call("adding an address", waiter.retry_busy,
                      lambda: c.request("POST", c.vm_path(vm_id) + ":enable-additional-ip", body={}, retries=0))
        billing = (res or {}).get("billingMessage") or billing
        alloc = (res or {}).get("allocation") or {}
        addr = alloc.get("ipAddress")
        if not addr:
            def check():
                now = set(a["ip_address"] for a in ips(c.get_virtual_machine(vm_id)))
                new = sorted(now - known)
                return bool(new), (new[0] if new else None)

            addr = nr.call("waiting for the new address", waiter.wait, "the new address to be listed", check)
        added.append(addr)

    def settled():
        now = ips(c.get_virtual_machine(vm_id))
        addrs = [a["ip_address"] for a in now]
        return (all(a in addrs for a in added) and not any(a in addrs for a in removed)), now

    after = nr.call("waiting for the addresses", waiter.wait, "the addresses to be updated", settled)
    result = dict(changed=True, additional_ips=after, added=added, removed=removed,
                  diff=dict(before=dict(additional_ips=have_addrs), after=dict(additional_ips=[a["ip_address"] for a in after])))
    if billing:
        result["billing_message"] = billing
    module.exit_json(**result)


if __name__ == "__main__":
    main()
