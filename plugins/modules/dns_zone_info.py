#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: dns_zone_info
short_description: List NodeRings DNS zones
version_added: 0.1.0
description:
  - Lists the organization's hosted DNS zones, optionally only one by name or ID, with its DNSSEC state.
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
      - Only return the zone with this name.
    type: str
  id:
    description:
      - Only return the zone with this ID.
    type: str
  include_dnssec:
    description:
      - Also return each zone's DNSSEC state (one extra request per zone).
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: List all zones
  noderings.cloud.dns_zone_info:
  register: zones

- name: Get one zone with its DS record
  noderings.cloud.dns_zone_info:
    name: example.com
    include_dnssec: true
  register: zone
"""

RETURN = r"""
zones:
  description: The matching zones. With O(include_dnssec=true) each has a C(dnssec) key.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.dns import normalize_zone_name
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    snake,
)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(name=dict(type="str"), id=dict(type="str"), include_dnssec=dict(type="bool", default=False))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    zones = nr.call("listing DNS zones", nr.client.list_dns_zones)
    name = normalize_zone_name(module.params["name"]) if module.params["name"] else None
    zid = module.params["id"]
    zones = [z for z in zones if (not name or normalize_zone_name(z.get("name")) == name) and (not zid or z.get("id") == zid)]
    out = []
    for z in zones:
        item = snake(z)
        if module.params["include_dnssec"]:
            item["dnssec"] = snake(nr.call("reading DNSSEC for %s" % z.get("name"), nr.client.get_dnssec, z["id"]))
        out.append(item)
    module.exit_json(changed=False, zones=out)


if __name__ == "__main__":
    main()
