#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: marketplace_region_info
short_description: List the cities where the NodeRings marketplace has offers
version_added: 0.1.0
description:
  - Lists every country and city where at least one hosting provider sells servers.
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
  asset_type:
    description:
      - Only cities with offers for this kind of product.
    type: str
    choices: [virtual_machine, game_server]
"""

EXAMPLES = r"""
- name: Where can I run a VM?
  noderings.cloud.marketplace_region_info:
    asset_type: virtual_machine
  register: regions
"""

RETURN = r"""
regions:
  description: Countries and cities.
  returned: always
  type: list
  elements: dict
  sample:
    - country: Germany
      city: Frankfurt
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import ASSET_TYPES
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(asset_type=dict(type="str", choices=list(ASSET_TYPES)))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    regions = nr.call("listing regions", nr.client.list_marketplace_regions, ASSET_TYPES.get(module.params["asset_type"] or ""))
    out = sorted((dict(country=r.get("country"), city=r.get("city")) for r in regions), key=lambda r: (r["country"] or "", r["city"] or ""))
    module.exit_json(changed=False, regions=out)


if __name__ == "__main__":
    main()
