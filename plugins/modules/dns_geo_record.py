#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: dns_geo_record
short_description: Manage geo-routed DNS records in a NodeRings zone
version_added: 0.1.0
description:
  - A geo-routed record answers differently depending on where the resolver is.
  - The most specific match wins, region before country before continent, and O(default) answers everyone else.
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
      - Record name relative to the zone. Use C(@) for the apex.
    type: str
    required: true
  type:
    description:
      - Record type.
    type: str
    required: true
    choices: [A, AAAA, CNAME, NAPTR, SRV]
  ttl:
    description:
      - Time to live in seconds, 30 to 60.
    type: int
    default: 60
  default:
    description:
      - Answer for resolvers that match no other rule. Required when O(state=present).
    type: str
  continents:
    description:
      - Answers by continent code (C(AF), C(AN), C(AS), C(EU), C(NA), C(OC), C(SA)).
    type: dict
    default: {}
  countries:
    description:
      - Answers by ISO 3166-1 alpha-2 country code, for example C(DE).
    type: dict
    default: {}
  regions:
    description:
      - Answers by ISO 3166-2 subdivision such as C(US-CA), or a region group such as C(US-IX).
    type: dict
    default: {}
  state:
    description:
      - Whether the record should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Send Europe and North America to the nearest server
  noderings.cloud.dns_geo_record:
    zone: example.com
    name: app
    type: A
    default: 203.0.113.10
    continents:
      EU: 198.51.100.20
      NA: 203.0.113.10
    countries:
      JP: 192.0.2.30
"""

RETURN = r"""
geo_record:
  description: The record as stored. Empty after O(state=absent).
  returned: always
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.dns import GEO_RECORD_TYPES, canonical, find_zone, relative_name
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
)


def view(zone_id, rel, rrtype, g):
    if not g:
        return {}
    return dict(zone_id=zone_id, name=rel, type=rrtype, ttl=int_or_zero(g.get("ttl")), default=g.get("defaultRdata") or "",
                continents=dict(g.get("continents") or {}), countries=dict(g.get("countries") or {}), regions=dict(g.get("regions") or {}))


def canon_map(rrtype, m, upper_keys=True):
    return dict(((k.upper() if upper_keys else k), canonical(rrtype, v)) for k, v in (m or {}).items())


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        zone=dict(type="str"),
        zone_id=dict(type="str"),
        name=dict(type="str", required=True),
        type=dict(type="str", required=True, choices=GEO_RECORD_TYPES),
        ttl=dict(type="int", default=60),
        default=dict(type="str"),
        continents=dict(type="dict", default={}),
        countries=dict(type="dict", default={}),
        regions=dict(type="dict", default={}),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[("zone", "zone_id")],
        mutually_exclusive=[("zone", "zone_id")],
        required_if=[("state", "present", ["default"])],
        supports_check_mode=True,
    )
    p = module.params
    if not 30 <= p["ttl"] <= 60:
        module.fail_json(msg="ttl must be between 30 and 60 seconds for geo records")
    nr = NodeRingsModule(module)
    zone = find_zone(nr, p["zone"], p["zone_id"])
    zone_id = zone["id"]
    rrtype = p["type"]
    rel = relative_name(p["name"], zone.get("name"))
    geo = nr.call("listing geo records", nr.client.list_dns_geo_records, zone_id)
    current = next((g for g in geo if relative_name(g.get("name"), "") == rel and (g.get("type") or "").upper() == rrtype), None)
    before = view(zone_id, rel, rrtype, current)

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, geo_record={})
        if not module.check_mode:
            try:
                nr.client.delete_dns_geo_record(zone_id, rel, rrtype)
            except NodeRingsError as e:
                if e.code != 5:
                    nr.fail("deleting geo record %s %s" % (rel, rrtype), e)
        module.exit_json(changed=True, geo_record={}, diff=dict(before=before, after={}))

    def s(m):
        return dict((str(k).upper(), str(v).strip()) for k, v in (m or {}).items())

    after = dict(zone_id=zone_id, name=rel, type=rrtype, ttl=p["ttl"], default=p["default"].strip(),
                 continents=s(p["continents"]), countries=s(p["countries"]), regions=s(p["regions"]))
    if current and before["ttl"] == after["ttl"] and canonical(rrtype, before["default"]) == canonical(rrtype, after["default"]) and all(
        canon_map(rrtype, before[k]) == canon_map(rrtype, after[k]) for k in ("continents", "countries", "regions")
    ):
        module.exit_json(changed=False, geo_record=before)

    if not module.check_mode:
        body = dict(name=rel, type=rrtype, ttl=p["ttl"], defaultRdata=after["default"],
                    continents=after["continents"], countries=after["countries"], regions=after["regions"])
        nr.call("writing geo record %s %s" % (rel, rrtype), nr.client.upsert_dns_geo_record, zone_id, body)
        geo = nr.call("listing geo records", nr.client.list_dns_geo_records, zone_id)
        stored = next((g for g in geo if relative_name(g.get("name"), "") == rel and (g.get("type") or "").upper() == rrtype), None)
        after = view(zone_id, rel, rrtype, stored) or after
    module.exit_json(changed=True, geo_record=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
