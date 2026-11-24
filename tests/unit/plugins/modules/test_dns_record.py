# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import dns_record

ZONE = {"id": "z1", "name": "example.com"}


def dns_api(api, records):
    @api.route("GET", "/v1/dns/zones")
    def zones(q, b):
        return 200, {"zones": [ZONE]}

    @api.route("GET", "/v1/dns/zones/z1/records")
    def lst(q, b):
        return 200, {"records": records, "totalCount": len(records)}

    @api.route("PUT", "/v1/dns/zones/z1/records")
    def put(q, b):
        rec = b["record"]
        records[:] = [r for r in records if not (r["name"] == rec["name"] and r["type"] == rec["type"])] + [rec]
        return 200, rec

    @api.route("DELETE", "/v1/dns/zones/z1/records")
    def delete(q, b):
        records[:] = [r for r in records if not (r["name"] == q["name"] and r["type"] == q["type"])]
        return 200, {}


def test_dns_record_lifecycle(api, run):
    records = [{"name": "@", "type": "NS", "ttl": "3600", "rdata": ["ns1."], "system": True}]
    dns_api(api, records)
    args = dict(zone="Example.com.", name="www.example.com", type="TXT", ttl=300, values=["hello world"])
    r = run(dns_record, args)
    assert r["changed"] and r["record"]["values"] == ["hello world"]
    assert records[-1]["rdata"] == ['"hello world"']
    assert not run(dns_record, args)["changed"]
    r = run(dns_record, dict(args, values=["second"], append=True))
    assert r["changed"] and sorted(r["record"]["values"]) == ["hello world", "second"]
    r = run(dns_record, dict(args, values=["second"], append=True, state="absent"))
    assert r["changed"] and r["record"]["values"] == ["hello world"]
    assert run(dns_record, dict(args, state="absent"))["changed"]
    assert len(records) == 1  # the system NS record is untouched


def test_dns_record_unknown_zone(api, run):
    dns_api(api, [])
    r = run(dns_record, dict(zone="other.com", name="www", type="A", values=["192.0.2.1"]))
    assert r["failed"] and "does not exist" in r["msg"]
