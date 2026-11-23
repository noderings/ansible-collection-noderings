#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: marketplace_provider_info
short_description: List NodeRings hosting providers, or read one provider's catalog
version_added: 0.1.0
description:
  - Without O(id) or O(storefront_slug), lists the hosting providers on the marketplace with their ratings and capabilities.
  - With O(id) or O(storefront_slug), returns that provider's cities and plans.
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
      - Return this provider's catalog.
    type: str
  storefront_slug:
    description:
      - Return the catalog of the provider with this public storefront, with the storefront's details.
    type: str
  asset_type:
    description:
      - When listing, only providers that sell this kind of product.
    type: str
    choices: [virtual_machine, game_server]
  search:
    description:
      - When listing, only providers whose name matches this text.
    type: str
"""

EXAMPLES = r"""
- name: Providers that sell VMs
  noderings.cloud.marketplace_provider_info:
    asset_type: virtual_machine
  register: providers

- name: One provider's catalog
  noderings.cloud.marketplace_provider_info:
    id: "{{ vm.virtual_machine.provider_organization_id }}"
  register: provider
"""

RETURN = r"""
providers:
  description: The providers, when listing.
  returned: always
  type: list
  elements: dict
provider:
  description: The provider with its regions and plans, when O(id) or O(storefront_slug) is set.
  returned: when O(id) or O(storefront_slug) is set
  type: dict
storefront:
  description: The public storefront, when O(storefront_slug) is set.
  returned: when O(storefront_slug) is set
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import ASSET_TYPES
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake

PROVIDER_KEYS = ("organizationId", "organizationName", "description", "rating", "totalReviews", "platformDriver", "capabilities", "providerLogoUrl")


def provider_summary(p):
    return snake(dict((k, p.get(k)) for k in PROVIDER_KEYS))


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        id=dict(type="str"),
        storefront_slug=dict(type="str"),
        asset_type=dict(type="str", choices=list(ASSET_TYPES)),
        search=dict(type="str"),
    )
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[("id", "storefront_slug")], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    result = dict(changed=False, providers=[])
    provider_id = p["id"]
    if p["storefront_slug"]:
        sf = nr.call("reading storefront %s" % p["storefront_slug"], c.get_public_storefront, p["storefront_slug"])
        if not sf:
            module.fail_json(msg="no storefront is named %s" % p["storefront_slug"])
        result["storefront"] = snake(dict((k, v) for k, v in sf.items() if k != "catalog"))
        provider_id = sf.get("providerId")
    if provider_id:
        d = nr.call("reading provider %s" % provider_id, c.get_provider, provider_id)
        if not d:
            module.fail_json(msg="provider %s was not found" % provider_id)
        out = provider_summary(d.get("provider") or {})
        out.update(snake(dict(website=d.get("website"), availableRegions=d.get("availableRegions"), hasIpv6=d.get("hasIpv6"),
                              availablePlans=d.get("availablePlans"))))
        result["provider"] = out
        module.exit_json(**result)
    providers = nr.call("listing providers", c.list_provider_directory, ASSET_TYPES.get(p["asset_type"] or ""), p["search"])
    result["providers"] = [provider_summary(x) for x in providers]
    module.exit_json(**result)


if __name__ == "__main__":
    main()
