#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: marketplace_plan_info
short_description: List plan codes sold on the NodeRings marketplace, or read one plan
version_added: 0.1.0
description:
  - Without O(plan_id), lists the plan codes that are for sale, optionally only in one city or of one billing type.
  - With O(plan_id), returns that provider plan with its size and prices.
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
  plan_id:
    description:
      - Return this plan instead of listing plan codes.
    type: str
  country:
    description:
      - Only plan codes sold in this country.
    type: str
  city:
    description:
      - Only plan codes sold in this city.
    type: str
  billing_type:
    description:
      - Only plan codes with this billing type.
    type: str
    choices: [usage, subscription, free]
  asset_type:
    description:
      - Only plan codes for this kind of product.
    type: str
    choices: [virtual_machine, game_server]
"""

EXAMPLES = r"""
- name: Hourly VM sizes sold in Frankfurt
  noderings.cloud.marketplace_plan_info:
    country: Germany
    city: Frankfurt
    billing_type: usage
    asset_type: virtual_machine
  register: plans

- name: Size and prices of one plan
  noderings.cloud.marketplace_plan_info:
    plan_id: "{{ vm.virtual_machine.plan_id }}"
  register: plan
"""

RETURN = r"""
plan_codes:
  description: The plan codes. Empty when O(plan_id) is set.
  returned: always
  type: list
  elements: dict
  sample:
    - plan_code: SC-GC-1C-1G-20
      billing_type: usage
      compute_type: COMPUTE_TYPE_SHARED
      compute_category: COMPUTE_CATEGORY_GENERAL
plan:
  description: The plan. Returned when O(plan_id) is set.
  returned: when O(plan_id) is set
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import ASSET_TYPES, BILLING_TYPES, price_view
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake, trim_enum


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        plan_id=dict(type="str"),
        country=dict(type="str"),
        city=dict(type="str"),
        billing_type=dict(type="str", choices=list(BILLING_TYPES)),
        asset_type=dict(type="str", choices=list(ASSET_TYPES)),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    p = module.params
    if p["plan_id"]:
        plan = nr.call("reading plan %s" % p["plan_id"], nr.client.get_marketplace_plan, p["plan_id"])
        if not plan or not plan.get("planId"):
            module.fail_json(msg="plan %s was not found" % p["plan_id"])
        out = snake(dict((k, v) for k, v in plan.items() if k != "planPrices"))
        out["billing_type"] = trim_enum(plan.get("billingType"), "BILLING_TYPE_")
        out["prices"] = [price_view(x) for x in plan.get("planPrices") or []]
        module.exit_json(changed=False, plan=out, plan_codes=[])
    codes = nr.call("listing plan codes", nr.client.list_available_plans, p["country"], p["city"],
                    BILLING_TYPES.get(p["billing_type"] or ""), ASSET_TYPES.get(p["asset_type"] or ""))
    out = []
    for c in codes:
        item = snake(c)
        item["billing_type"] = trim_enum(c.get("billingType"), "BILLING_TYPE_")
        out.append(item)
    module.exit_json(changed=False, plan_codes=out)


if __name__ == "__main__":
    main()
