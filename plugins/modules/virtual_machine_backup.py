#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: virtual_machine_backup
short_description: Turn automatic backups of a NodeRings virtual machine on or off
version_added: 0.1.0
description:
  - Subscribes a virtual machine to one of its hosting provider's backup add-ons, or cancels it.
  - B(Billing.) The add-on is billed with the VM. On usage-billed VMs it is charged per GB-hour of backup storage.
  - Cancelling the add-on (O(state=absent)) takes effect immediately and B(deletes all of the VM's backups).
    Reinstalling the VM also cancels it.
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
  addon:
    description:
      - Code of the backup add-on, for example C(DAILY-BACKUP) or C(WEEKLY-BACKUP).
      - Defaults to the only backup add-on the provider sells; required when it sells several.
      - See M(noderings.cloud.marketplace_addon_info).
    type: str
  addon_id:
    description:
      - ID of the backup add-on. Mutually exclusive with O(addon).
    type: str
  state:
    description:
      - V(present) subscribes the VM to the add-on (switching from another backup add-on if needed).
      - V(absent) cancels backups and deletes the VM's backups.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Daily backups for the database server
  noderings.cloud.virtual_machine_backup:
    vm: db-1
    addon: DAILY-BACKUP
"""

RETURN = r"""
backup:
  description: The active backup add-on subscription. Empty when backups are off.
  returned: always
  type: dict
  sample:
    addon_code: DAILY-BACKUP
    addon_id: 1f2e3d4c-0000-0000-0000-000000000000
    addon_name: Daily backup
    addon_status: active
    unit_amount: "0.000041"
    currency: USD
"""

import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import resolve_vm
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    Waiter,
    noderings_argument_spec,
    snake,
    trim_enum,
)

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def active_backup(vm):
    for a in vm.get("addonSubscriptions") or []:
        if a.get("addonType") in ("ADDON_TYPE_BACKUP", "ADDON_TYPE_SNAPSHOT") and a.get("addonStatus") == "ADDON_STATUS_ACTIVE":
            return a
    return None


def view(a):
    if not a:
        return {}
    out = snake(a)
    out["addon_status"] = trim_enum(a.get("addonStatus"), "ADDON_STATUS_")
    out["addon_type"] = trim_enum(a.get("addonType"), "ADDON_TYPE_")
    return out


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        virtual_machine=dict(type="str", required=True, aliases=["vm"]),
        addon=dict(type="str"),
        addon_id=dict(type="str"),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[("addon", "addon_id")], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    ref = p["virtual_machine"]
    is_id = bool(UUID_RE.match(ref))
    vm = resolve_vm(nr, ref if is_id else None, None if is_id else ref)
    vm_id = vm["id"]
    current = active_backup(vm)
    before = view(current)
    waiter = Waiter(600)

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, backup={})
        if not module.check_mode:
            nr.call("cancelling backups", waiter.retry_busy,
                    lambda: c.request("POST", c.vm_path(vm_id) + ":disable-backup",
                                      body={"addonId": current.get("addonId"), "cancelImmediately": True}))
        module.exit_json(changed=True, backup={}, diff=dict(before=before, after={}))

    addons = nr.call("listing backup add-ons", c.list_available_addons, vm_id, None, "ADDON_TYPE_BACKUP")
    if p["addon_id"]:
        addon = next((a for a in addons if a.get("id") == p["addon_id"]), None)
    elif p["addon"]:
        addon = next((a for a in addons if a.get("code") == p["addon"]), None)
    elif len(addons) == 1:
        addon = addons[0]
    else:
        addon = None
        module.fail_json(msg="the provider of %s sells %d backup add-ons; choose one with addon: %s" % (
            vm.get("hostname"), len(addons), ", ".join(sorted(set(a.get("code") or "" for a in addons)))))
    if not addon:
        module.fail_json(msg="backup add-on %s is not sold for %s; available: %s" % (
            p["addon"] or p["addon_id"], vm.get("hostname"), ", ".join(sorted(set(a.get("code") or "" for a in addons))) or "none"))

    if current and current.get("addonId") == addon.get("id"):
        module.exit_json(changed=False, backup=before)
    after = dict(addon_id=addon.get("id"), addon_code=addon.get("code"), addon_name=addon.get("name"), addon_status="active")
    if module.check_mode:
        module.exit_json(changed=True, backup=after, diff=dict(before=before, after=after))
    if current:
        nr.call("cancelling the previous backup add-on", waiter.retry_busy,
                lambda: c.request("POST", c.vm_path(vm_id) + ":disable-backup", body={"addonId": current.get("addonId"), "cancelImmediately": True}))
    nr.call("enabling backups", waiter.retry_busy, lambda: c.request("POST", c.vm_path(vm_id) + ":enable-backup", body={"addonId": addon.get("id")}))

    def check():
        v = c.get_virtual_machine(vm_id)
        a = active_backup(v)
        return bool(a and a.get("addonId") == addon.get("id")), a

    found = nr.call("waiting for the backup add-on", waiter.wait, "the backup add-on to become active", check)
    after = view(found)
    module.exit_json(changed=True, backup=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
