#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: marketplace_offer_info
short_description: Find NodeRings marketplace offers for a plan code in a city
version_added: 0.1.0
description:
  - NodeRings is a marketplace. The same plan code is usually sold by several hosting providers,
    in several cities, at different prices. This module lists the offers for one plan code in one city,
    best first, and returns the best one as RV(offer).
  - Use RV(offer.plan_id) and RV(offer.region_id) with M(noderings.cloud.virtual_machine) or M(noderings.cloud.game_server)
    to order exactly that offer.
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
  plan_code:
    description:
      - Platform plan code, for example C(SC-GC-1C-1G-20). See M(noderings.cloud.marketplace_plan_info).
    type: str
    required: true
  country:
    description:
      - Country, for example C(Germany) (case-insensitive). See M(noderings.cloud.marketplace_region_info).
    type: str
    required: true
  city:
    description:
      - City, for example C(Frankfurt) (case-insensitive).
    type: str
    required: true
  billing_type:
    description:
      - V(usage) (billed hourly from credit), V(subscription) (billed monthly) or V(free).
      - Strongly recommended; without it each provider offers one plan of its choice for the code.
    type: str
    choices: [usage, subscription, free]
  asset_type:
    description:
      - What is ordered. Only checked when the provider is known (O(provider_id), O(storefront_slug), or O(provider)
        given as an ID or storefront slug).
    type: str
    choices: [virtual_machine, game_server]
    default: virtual_machine
  provider:
    description:
      - Only offers from this hosting provider, given by its provider ID, its storefront slug
        (for example C(acme-hosting)) or its name (for example C(Acme Hosting), in any case).
      - A name that more than one provider uses fails; give the provider ID or storefront slug then.
      - Mutually exclusive with O(provider_id) and O(storefront_slug).
    type: str
  provider_id:
    description:
      - Only offers from this provider.
    type: str
  storefront_slug:
    description:
      - Only offers from the provider with this public storefront, for example C(acme-hosting).
    type: str
  require_capabilities:
    description:
      - Only providers whose platform supports all of these, for example C(guest_firewall), C(on_demand_backup),
        C(snapshots) or C(instant_apps).
    type: list
    elements: str
    default: []
  require_ipv6:
    description:
      - Only offers with IPv6 in the city.
    type: bool
    default: false
  sort:
    description:
      - V(price) sorts by the compute price (cheapest first), V(rating) by the provider's rating (best first).
    type: str
    choices: [price, rating]
    default: price
  fail_if_none:
    description:
      - Fail when no offer matches. With V(false), RV(offer) is empty instead.
    type: bool
    default: true
"""

EXAMPLES = r"""
- name: Cheapest hourly 1 vCPU / 1 GB server in Ashburn with a firewall
  noderings.cloud.marketplace_offer_info:
    plan_code: SC-GC-1C-1G-20
    country: United States
    city: Ashburn
    billing_type: usage
    require_capabilities: [guest_firewall]
  register: found

- name: Offers from one provider, by name
  noderings.cloud.marketplace_offer_info:
    plan_code: SC-GC-1C-1G-20
    country: United States
    city: Ashburn
    billing_type: usage
    provider: Acme Hosting
  register: acme

- name: Order exactly that offer
  noderings.cloud.virtual_machine:
    hostname: web-1
    plan_id: "{{ found.offer.plan_id }}"
    region_id: "{{ found.offer.region_id }}"
"""

RETURN = r"""
offer:
  description: The best offer. Empty when none matched and O(fail_if_none=false).
  returned: always
  type: dict
  contains:
    provider_id:
      description: ID of the hosting provider.
      type: str
    provider_name:
      description: Name of the hosting provider.
      type: str
    plan_id:
      description: ID of the provider's plan for the code.
      type: str
    region_id:
      description: ID of the city at that provider.
      type: str
    billing_type:
      description: C(usage), C(subscription) or C(free).
      type: str
    capabilities:
      description: What the provider's platform supports.
      type: list
      elements: str
    rating:
      description: Provider rating.
      type: float
    prices:
      description: Price lines of the plan.
      type: list
      elements: dict
offers:
  description: Every matching offer, best first.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import (
    NoOfferError,
    find_offers,
    no_offer_message,
    offer_view,
)
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsError, NodeRingsModule, noderings_argument_spec


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        plan_code=dict(type="str", required=True),
        country=dict(type="str", required=True),
        city=dict(type="str", required=True),
        billing_type=dict(type="str", choices=["usage", "subscription", "free"]),
        asset_type=dict(type="str", default="virtual_machine", choices=["virtual_machine", "game_server"]),
        provider=dict(type="str"),
        provider_id=dict(type="str"),
        storefront_slug=dict(type="str"),
        require_capabilities=dict(type="list", elements="str", default=[]),
        require_ipv6=dict(type="bool", default=False),
        sort=dict(type="str", default="price", choices=["price", "rating"]),
        fail_if_none=dict(type="bool", default=True),
    )
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[("provider", "provider_id", "storefront_slug")], supports_check_mode=True)
    nr = NodeRingsModule(module)
    p = module.params
    try:
        offers, located = find_offers(nr.client, p["plan_code"], p["country"], p["city"], billing_type=p["billing_type"],
                                      asset_type=p["asset_type"], provider_id=p["provider_id"], storefront_slug=p["storefront_slug"],
                                      require_capabilities=p["require_capabilities"], require_ipv6=p["require_ipv6"], sort=p["sort"],
                                      provider=p["provider"])
    except (NodeRingsError, NoOfferError) as e:
        nr.fail("looking up offers", e)
    views = [offer_view(o) for o in offers]
    if not views and p["fail_if_none"]:
        module.fail_json(msg=no_offer_message(p["plan_code"], p["country"], p["city"], p["billing_type"], located,
                                              p["provider"] or p["provider_id"] or p["storefront_slug"]))
    module.exit_json(changed=False, offer=views[0] if views else {}, offers=views)


if __name__ == "__main__":
    main()
