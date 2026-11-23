#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: marketplace_addon_info
short_description: List add-ons sold on the NodeRings marketplace
version_added: 0.1.0
description:
  - Lists add-ons such as backups and additional IP addresses, with their prices.
  - With O(virtual_machine), lists the add-ons the VM's hosting provider sells for that VM.
  - One of O(virtual_machine) or O(provider_id) is required.
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
  virtual_machine:
    description:
      - Hostname or ID of a VM. Only add-ons for that VM.
    type: str
    aliases: [vm]
  provider_id:
    description:
      - Only add-ons from this provider.
    type: str
  addon_type:
    description:
      - Only add-ons of this type.
    type: str
    choices: [backup, additional_ip, snapshot]
  billing_type:
    description:
      - Only add-ons with this billing type.
    type: str
    choices: [usage, subscription, free]
  code:
    description:
      - Only add-ons with this code, for example C(DAILY-BACKUP).
    type: str
"""

EXAMPLES = r"""
- name: Backup options for a VM
  noderings.cloud.marketplace_addon_info:
    vm: db-1
    addon_type: backup
  register: backups
"""

RETURN = r"""
addons:
  description: The add-ons.
  returned: always
  type: list
  elements: dict
  sample:
    - id: 1f2e3d4c-0000-0000-0000-000000000000
      code: DAILY-BACKUP
      name: Daily backup
      addon_type: backup
      prices:
        - unit_amount: "0.000041"
          currency: USD
          unit_name: per GB-hour
          billing_period: month
          pricing_model: usage_based
"""

import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import resolve_vm
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import BILLING_TYPES
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, trim_enum

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        virtual_machine=dict(type="str", aliases=["vm"]),
        provider_id=dict(type="str"),
        addon_type=dict(type="str", choices=["backup", "additional_ip", "snapshot"]),
        billing_type=dict(type="str", choices=list(BILLING_TYPES)),
        code=dict(type="str"),
    )
    module = AnsibleModule(argument_spec=argument_spec, required_one_of=[("virtual_machine", "provider_id")], supports_check_mode=True)
    nr = NodeRingsModule(module)
    p = module.params
    vm_id = None
    if p["virtual_machine"]:
        ref = p["virtual_machine"]
        vm_id = resolve_vm(nr, ref if UUID_RE.match(ref) else None, None if UUID_RE.match(ref) else ref)["id"]
    addon_type = "ADDON_TYPE_" + p["addon_type"].upper() if p["addon_type"] else None
    addons = nr.call("listing add-ons", nr.client.list_available_addons, vm_id, p["provider_id"], addon_type,
                     BILLING_TYPES.get(p["billing_type"] or ""))
    out = []
    for a in addons:
        if p["code"] and a.get("code") != p["code"]:
            continue
        out.append(dict(
            id=a.get("id"), code=a.get("code"), name=a.get("name"), description=a.get("description"),
            addon_type=trim_enum(a.get("addonType"), "ADDON_TYPE_"), compatible_plan_codes=a.get("compatiblePlanCodes") or [],
            prices=[dict(unit_amount=x.get("unitAmount") or "", currency=x.get("currency") or "", unit_name=x.get("unitName") or "",
                         billing_period=trim_enum(x.get("billingPeriod"), "BILLING_PERIOD_"),
                         pricing_model=trim_enum(x.get("pricingModel"), "PRICING_MODEL_")) for x in a.get("addonPrices") or []],
        ))
    module.exit_json(changed=False, addons=out)


if __name__ == "__main__":
    main()
