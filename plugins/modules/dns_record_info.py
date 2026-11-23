#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: dns_record_info
short_description: List DNS records in a NodeRings zone
version_added: 0.1.0
description:
  - Lists the record sets of a NodeRings DNS zone, including geo-routed records.
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
  zone:
    description:
      - Name of the zone. Either O(zone) or O(zone_id) is required.
    type: str
  zone_id:
    description:
      - ID of the zone.
    type: str
  name:
    description:
      - Only return records with exactly this name (relative to the zone, C(@) for the apex).
    type: str
  type:
    description:
      - Only return records of this type.
    type: str
  include_system:
    description:
      - Also return records the platform manages itself (the apex SOA and NS records).
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Dump a zone
  noderings.cloud.dns_record_info:
    zone: example.com
  register: records

- name: Get the MX records
  noderings.cloud.dns_record_info:
    zone: example.com
    name: "@"
    type: MX
  register: mx
"""

RETURN = r"""
records:
  description: The record sets.
  returned: always
  type: list
  elements: dict
  sample:
    - name: www
      type: A
      ttl: 300
      values: [203.0.113.10]
      system: false
geo_records:
  description: Geo-routed record sets in the zone.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.dns import find_zone, from_api, relative_name
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
    snake,
)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        zone=dict(type="str"),
        zone_id=dict(type="str"),
        name=dict(type="str"),
        type=dict(type="str"),
        include_system=dict(type="bool", default=False),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[("zone", "zone_id")],
        mutually_exclusive=[("zone", "zone_id")],
        supports_check_mode=True,
    )
    p = module.params
    nr = NodeRingsModule(module)
    zone = find_zone(nr, p["zone"], p["zone_id"])
    rel = relative_name(p["name"], zone.get("name")) if p["name"] else None
    rrtype = (p["type"] or "").upper() or None
    recs = nr.call("listing DNS records", nr.client.list_dns_records, zone["id"], None if rel in (None, "@") else rel, rrtype)
    out = []
    for r in recs:
        t = (r.get("type") or "").upper()
        n = relative_name(r.get("name"), "")
        if (rel and n != rel) or (rrtype and t != rrtype) or (r.get("system") and not p["include_system"]):
            continue
        out.append(dict(name=n, type=t, ttl=int_or_zero(r.get("ttl")), values=[from_api(t, v) for v in r.get("rdata") or []],
                        system=bool(r.get("system"))))
    geo = nr.call("listing geo records", nr.client.list_dns_geo_records, zone["id"])
    geo = [snake(g) for g in geo if (not rel or relative_name(g.get("name"), "") == rel) and (not rrtype or (g.get("type") or "").upper() == rrtype)]
    module.exit_json(changed=False, records=out, geo_records=geo)


if __name__ == "__main__":
    main()
