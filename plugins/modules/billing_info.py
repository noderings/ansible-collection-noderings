#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: billing_info
short_description: Read a NodeRings organization's credit, subscriptions and plan limits
version_added: 0.1.0
description:
  - Returns the prepaid credit balance (which pays for usage-billed servers), the subscriptions,
    and the organization's entitlements (plan limits and current usage).
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
  only_active_subscriptions:
    description:
      - Only return active subscriptions.
    type: bool
    default: true
"""

EXAMPLES = r"""
- name: Stop if the credit is low
  noderings.cloud.billing_info:
  register: billing

- name: Check
  ansible.builtin.assert:
    that: billing.credit.available | float > 1
    fail_msg: "Only {{ billing.credit.available }} {{ billing.credit.currency }} credit left"
"""

RETURN = r"""
credit:
  description: The credit balance. Amounts are decimal strings.
  returned: always
  type: dict
  sample:
    balance: "9.965000"
    reserved: "0.000000"
    available: "9.965000"
    currency: USD
    frozen: false
subscriptions:
  description: Subscriptions, one per billed resource.
  returned: always
  type: list
  elements: dict
entitlements:
  description: Plan limits and how much of each is used.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake, trim_enum


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(only_active_subscriptions=dict(type="bool", default=True))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    credit = snake(nr.call("reading the credit balance", c.get_credit_balance))
    subs = []
    for s in nr.call("listing subscriptions", c.list_subscriptions, module.params["only_active_subscriptions"]):
        item = snake(s)
        item["subscription_status"] = trim_enum(s.get("subscriptionStatus"), "SUBSCRIPTION_STATUS_")
        item["billing_type"] = trim_enum(s.get("billingType"), "BILLING_TYPE_")
        subs.append(item)
    ents = snake(nr.call("reading entitlements", c.get_entitlements))
    module.exit_json(changed=False, credit=credit, subscriptions=subs, entitlements=ents)


if __name__ == "__main__":
    main()
