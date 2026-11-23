#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: dns_record
short_description: Manage DNS records in a NodeRings zone
version_added: 0.1.0
description:
  - Manages one record set (RRset) in a NodeRings DNS zone, that is all values for one name and type.
  - With O(state=present) the record set is made to hold exactly O(values), unless O(append=true).
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
      - Name of the zone, for example C(example.com). Either O(zone) or O(zone_id) is required.
    type: str
  zone_id:
    description:
      - ID of the zone.
    type: str
  name:
    description:
      - Record name relative to the zone, for example C(www). Use C(@) for the zone apex.
      - A fully qualified name inside the zone, such as C(www.example.com), also works.
    type: str
    required: true
  type:
    description:
      - Record type.
    type: str
    required: true
    choices: [A, AAAA, ALIAS, CAA, CERT, CNAME, DNAME, DS, HINFO, HTTPS, LOC, MX, NAPTR, NS, OPENPGPKEY,
              PTR, RP, SMIMEA, SRV, SSHFP, SVCB, TLSA, TXT]
  ttl:
    description:
      - Time to live in seconds.
    type: int
    default: 3600
  values:
    description:
      - The record values. Required when O(state=present).
      - Hostnames should end with a dot, for example C(10 mail.example.com.) for MX.
      - Write TXT values unquoted; long values are split into 255-byte strings for you.
    type: list
    elements: str
    aliases: [value, records]
  append:
    description:
      - With O(state=present), add O(values) to the record set instead of replacing it.
      - With O(state=absent), remove only O(values) from the record set instead of deleting it.
    type: bool
    default: false
  state:
    description:
      - Whether the record set should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Point www at a server
  noderings.cloud.dns_record:
    zone: example.com
    name: www
    type: A
    ttl: 300
    values: ["{{ vm.virtual_machine.ipv4 }}"]

- name: Mail for the apex
  noderings.cloud.dns_record:
    zone: example.com
    name: "@"
    type: MX
    values:
      - "10 mail1.example.com."
      - "20 mail2.example.com."

- name: Add one more SPF include without touching other TXT values
  noderings.cloud.dns_record:
    zone: example.com
    name: "@"
    type: TXT
    values: ["google-site-verification=abc123"]
    append: true

- name: Remove a record set
  noderings.cloud.dns_record:
    zone: example.com
    name: old
    type: CNAME
    state: absent
"""

RETURN = r"""
record:
  description: The record set as stored. Empty after it is deleted.
  returned: always
  type: dict
  sample:
    zone_id: 0f3c7b9e-1111-4c4c-8a8a-123456789abc
    name: www
    type: A
    ttl: 300
    values: [203.0.113.10]
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.dns import (
    RECORD_TYPES,
    canonical,
    find_zone,
    from_api,
    relative_name,
    same_values,
    to_api,
    validate_values,
)
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
)


def find_record(nr, zone_id, rel, rrtype):
    """The RRset with exactly this name and type, or None (the API's name filter is a substring match)."""
    recs = nr.call("listing DNS records", nr.client.list_dns_records, zone_id, "" if rel == "@" else rel, rrtype)
    for r in recs:
        if relative_name(r.get("name"), "") == rel and (r.get("type") or "").upper() == rrtype and not r.get("system"):
            return r
    return None


def view(zone_id, rel, rrtype, rec):
    if not rec:
        return {}
    return dict(zone_id=zone_id, name=rel, type=rrtype, ttl=int_or_zero(rec.get("ttl")),
                values=[from_api(rrtype, v) for v in rec.get("rdata") or []])


def write_error(err):
    msg = str(err)
    if isinstance(err, NodeRingsError) and err.status == 503:
        msg += (". The DNS backend rejected the change. Check the values: hostnames should end with a dot,"
                " and values must match the record type.")
    return msg


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        zone=dict(type="str"),
        zone_id=dict(type="str"),
        name=dict(type="str", required=True),
        type=dict(type="str", required=True, choices=RECORD_TYPES),
        ttl=dict(type="int", default=3600),
        values=dict(type="list", elements="str", aliases=["value", "records"]),
        append=dict(type="bool", default=False),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[("zone", "zone_id")],
        mutually_exclusive=[("zone", "zone_id")],
        required_if=[("state", "present", ["values"]), ("append", True, ["values"])],
        supports_check_mode=True,
    )
    p = module.params
    if not 30 <= p["ttl"] <= 86400:
        module.fail_json(msg="ttl must be between 30 and 86400 seconds")
    nr = NodeRingsModule(module)
    zone = find_zone(nr, p["zone"], p["zone_id"])
    zone_id = zone["id"]
    rrtype = p["type"]
    rel = relative_name(p["name"], zone.get("name"))
    current = find_record(nr, zone_id, rel, rrtype)
    before = view(zone_id, rel, rrtype, current)
    have = before.get("values", [])

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, record={})
        if p["append"]:
            drop = set(canonical(rrtype, v) for v in p["values"])
            keep = [v for v in have if canonical(rrtype, v) not in drop]
            if len(keep) == len(have):
                module.exit_json(changed=False, record=before)
            if keep:
                after = dict(before, values=keep)
                if not module.check_mode:
                    try:
                        nr.client.upsert_dns_record(zone_id, dict(name=rel, type=rrtype, ttl=before["ttl"],
                                                                  rdata=[to_api(rrtype, v) for v in keep]))
                    except Exception as e:  # pylint: disable=broad-except
                        module.fail_json(msg="updating DNS record %s %s: %s" % (rel, rrtype, write_error(e)))
                    after = view(zone_id, rel, rrtype, find_record(nr, zone_id, rel, rrtype))
                module.exit_json(changed=True, record=after, diff=dict(before=before, after=after))
        if not module.check_mode:
            try:
                nr.client.delete_dns_record(zone_id, rel, rrtype)
            except NodeRingsError as e:
                if e.code != 5:
                    module.fail_json(msg="deleting DNS record %s %s: %s" % (rel, rrtype, write_error(e)))
        module.exit_json(changed=True, record={}, diff=dict(before=before, after={}))

    wanted = [v.strip() for v in p["values"]]
    if p["append"]:
        seen = set(canonical(rrtype, v) for v in have)
        wanted = have + [v for v in wanted if canonical(rrtype, v) not in seen]
    err = validate_values(rrtype, wanted)
    if err:
        module.fail_json(msg="%s %s: %s" % (rel, rrtype, err))

    if current and before["ttl"] == p["ttl"] and same_values(rrtype, have, wanted):
        module.exit_json(changed=False, record=before)

    after = dict(zone_id=zone_id, name=rel, type=rrtype, ttl=p["ttl"], values=wanted)
    if not module.check_mode:
        try:
            nr.client.upsert_dns_record(zone_id, dict(name=rel, type=rrtype, ttl=p["ttl"], rdata=[to_api(rrtype, v) for v in wanted]))
        except Exception as e:  # pylint: disable=broad-except
            module.fail_json(msg="writing DNS record %s %s: %s" % (rel, rrtype, write_error(e)))
        stored = find_record(nr, zone_id, rel, rrtype)
        if not stored:
            module.fail_json(msg="The API accepted the change to %s %s but the record is not listed. Try again." % (rel, rrtype))
        after = view(zone_id, rel, rrtype, stored)
    module.exit_json(changed=True, record=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
