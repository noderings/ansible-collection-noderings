# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import io
import json

import pytest

from ansible.module_utils.six.moves.urllib.error import HTTPError

from ansible_collections.noderings.cloud.plugins.module_utils import dns, firewall, marketplace
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsClient,
    NodeRingsError,
    Waiter,
    TimeoutError_,
    decode_error,
    is_ambiguous,
    is_busy,
    snake,
    trim_enum,
)


class Resp(object):
    def __init__(self, body):
        self.body = body

    def read(self):
        return json.dumps(self.body).encode()


def http_error(status, body):
    return HTTPError("https://api", status, "x", {}, io.BytesIO(json.dumps(body).encode()))


def make_client(responses, **kw):
    calls = []

    def opener(url, **kwargs):
        calls.append((kwargs.get("method"), url, kwargs.get("headers"), kwargs.get("data")))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return Resp(r)

    c = NodeRingsClient(token="t", opener=opener, sleep=lambda s: None, **kw)
    return c, calls


def test_requires_token():
    with pytest.raises(ValueError):
        NodeRingsClient(token="")


def test_headers_and_query():
    c, calls = make_client([{"zones": []}], organization_id="org-1")
    c.list_dns_zones()
    method, url, headers, data = calls[0]
    assert method == "GET"
    assert url == "https://api.noderings.com/v1/dns/zones?page=0&pageSize=-1"
    assert headers["Authorization"] == "Bearer t"
    assert headers["X-Organization-ID"] == "org-1"


def test_retries_rate_limit_then_succeeds():
    c, calls = make_client([http_error(429, {"code": 8, "message": "slow down"}), {"sshKeys": [{"id": "1"}]}])
    assert c.list_ssh_keys() == [{"id": "1"}]
    assert len(calls) == 2


def test_quota_errors_are_not_retried():
    quota = {"code": 8, "message": "limit", "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "VM_LIMIT_REACHED",
                                                         "metadata": {"limit": "2", "current": "2", "limit_key": "vms"}}]}
    c, calls = make_client([http_error(429, quota)])
    with pytest.raises(NodeRingsError) as e:
        c.list_ssh_keys()
    assert len(calls) == 1
    assert "quota vms: 2 of 2 used" in str(e.value)


def test_writes_do_not_retry_503_but_reads_do():
    c, calls = make_client([http_error(503, {"message": "bad record"})])
    with pytest.raises(NodeRingsError):
        c.upsert_dns_record("z", {"name": "www"})
    assert len(calls) == 1
    c, calls = make_client([http_error(503, {}), {"zones": []}])
    assert c.list_dns_zones() == []
    assert len(calls) == 2


def test_orders_are_never_retried():
    c, calls = make_client([http_error(502, {})])
    with pytest.raises(NodeRingsError):
        c.create_virtual_machine({"hostname": "x"})
    assert len(calls) == 1


def test_decode_error_and_predicates():
    e = decode_error(404, b"not json")
    assert e.code == 5 and e.message == "not json"
    busy = decode_error(400, json.dumps({"code": 9, "message": "Operation in progress"}).encode())
    assert is_busy(busy)
    assert is_ambiguous(decode_error(504, b"{}"))
    assert not is_ambiguous(decode_error(400, b"{}"))


def test_snake_keeps_free_form_maps():
    out = snake({"planCode": "x", "metadata": {"someKey": 1}, "continents": {"EU": "a"}, "addonSubscriptions": [{"addonId": "1"}]})
    assert out == {"plan_code": "x", "metadata": {"someKey": 1}, "continents": {"EU": "a"}, "addon_subscriptions": [{"addon_id": "1"}]}
    assert trim_enum("BILLING_TYPE_USAGE", "BILLING_TYPE_") == "usage"
    assert trim_enum("BILLING_TYPE_UNSPECIFIED", "BILLING_TYPE_") == ""


def test_waiter_times_out():
    clock = [0.0]

    def sleep(s):
        clock[0] += s

    w = Waiter(10, interval=2, sleep=sleep, clock=lambda: clock[0])
    with pytest.raises(TimeoutError_):
        w.wait("never", lambda: (False, None))
    w = Waiter(10, sleep=sleep, clock=lambda: clock[0])
    seen = []
    assert w.wait("soon", lambda: (seen.append(1) or len(seen) == 3, "done")) == "done"


@pytest.mark.parametrize("rrtype,a,b,same", [
    ("A", ["203.0.113.1", "203.0.113.2"], ["203.0.113.2", "203.0.113.1"], True),
    ("CNAME", ["Target.example.com"], ["target.example.com."], True),
    ("MX", ["10 mail.example.com"], ["10 mail.example.com."], True),
    ("TXT", ["Hello"], ["hello"], False),
    ("AAAA", ["2001:db8::1"], ["2001:0db8:0:0::1"], True),
])
def test_dns_same_values(rrtype, a, b, same):
    assert dns.same_values(rrtype, a, b) is same


def test_dns_names_and_txt():
    assert dns.relative_name("www.Example.com.", "example.com") == "www"
    assert dns.relative_name("example.com", "example.com") == "@"
    assert dns.relative_name("", "example.com") == "@"
    long_value = "x" * 300 + ' "quoted"'
    quoted = dns.quote_txt(long_value)
    assert quoted.count('" "') == 1
    assert dns.unquote_txt(quoted) == long_value
    assert dns.validate_values("CNAME", ["a.", "b."])
    assert dns.validate_values("A", ["::1"])
    assert dns.validate_values("A", ["192.0.2.1"]) is None


def test_firewall_validation():
    ok = {"direction": "ingress", "action": "accept", "protocol": "tcp", "destination_ports": "443", "source": {"cidrs": ["0.0.0.0/0"]}}
    assert firewall.validate_rule(ok, 0) is None
    assert "no ports" in firewall.validate_rule(dict(ok, protocol="icmp"), 0)
    assert "one port" in firewall.validate_rule(dict(ok, destination_ports="80,443"), 0)
    assert "must be the only entry" in firewall.validate_rule(dict(ok, source={"cidrs": ["0.0.0.0/0", "10.0.0.0/8"]}), 0)
    assert "source or destination" in firewall.validate_rule(dict(ok, source=None), 0)
    assert "unknown protocol" in firewall.validate_rule(dict(ok, protocol="bogus"), 0)


class FakeRules(object):
    """Minimal ruleset store implementing the client calls reconcile() uses."""

    def __init__(self, bodies):
        self.rules = [{"id": "r%d" % i, "rule": b} for i, b in enumerate(bodies)]
        self.n = len(bodies)
        self.ops = []

    def list_firewall_rules(self, rs):
        return [dict(r, position=i) for i, r in enumerate(self.rules)]

    def update_firewall_rule(self, rid, body):
        self.ops.append(("update", rid))
        next(r for r in self.rules if r["id"] == rid)["rule"] = body

    def delete_firewall_rule(self, rid):
        self.ops.append(("delete", rid))
        self.rules = [r for r in self.rules if r["id"] != rid]

    def create_firewall_rule(self, rs, body):
        rid = "r%d" % self.n
        self.n += 1
        self.ops.append(("create", rid))
        self.rules.insert(0, {"id": rid, "rule": body})
        return {"id": rid}

    def move_firewall_rule(self, rid, target, position="FIREWALL_RULE_POSITION_BEFORE"):
        self.ops.append(("move", rid))
        r = next(x for x in self.rules if x["id"] == rid)
        self.rules.remove(r)
        self.rules.insert(next(i for i, x in enumerate(self.rules) if x["id"] == target), r)


def body(port):
    return firewall.rule_to_api({"direction": "ingress", "action": "accept", "protocol": "tcp", "destination_ports": str(port),
                                 "source": {"cidrs": ["0.0.0.0/0"]}}, {})


def test_reconcile_keeps_ids_and_order():
    store = FakeRules([body(22), body(80), body(443)])
    final = firewall.reconcile(store, "rs", [body(443), body(22), body(8080)])
    assert [r["rule"]["destinationPorts"] for r in final] == ["443", "22", "8080"]
    ids = [r["id"] for r in final]
    assert ids[0] == "r2" and ids[1] == "r0"
    assert ("update", "r1") in store.ops  # 80 became 8080 in place
    assert not any(op == "create" for op, rid in store.ops)


def test_reconcile_creates_and_deletes():
    store = FakeRules([body(22), body(80)])
    final = firewall.reconcile(store, "rs", [body(1), body(2), body(3)])
    assert [r["rule"]["destinationPorts"] for r in final] == ["1", "2", "3"]
    final = firewall.reconcile(store, "rs", [])
    assert final == []
    assert not firewall.plan_rules([], [])
    assert firewall.plan_rules(store.list_firewall_rules("rs"), [body(1)])


def test_main_price_prefers_compute_meter():
    prices = [{"unitAmount": "0.000041", "unitName": "per GB-hour"}, {"unitAmount": "0.007", "unitName": "per compute-hour"},
              {"unitAmount": "3", "unitName": "per GB"}]
    assert marketplace.main_price(prices) == 0.007
    assert marketplace.main_price([{"unitAmount": "5", "pricingModel": "PRICING_MODEL_FIXED"}, {"unitAmount": "0.1", "unitName": "per GB"}]) == 5
    assert marketplace.main_price([]) == float("inf")


class FakeMarket(object):
    def __init__(self, providers):
        self.providers = providers

    def list_providers(self, code, country, city, billing, ipv6):
        return self.providers


def provider(name, price, caps, rating=0.0):
    return {"organizationId": name, "organizationName": name, "planId": "plan-" + name, "capabilities": caps, "rating": rating,
            "planRegions": [{"regionId": "region-" + name, "country": "Germany", "city": "Frankfurt"}],
            "planPrices": [{"unitAmount": price, "unitName": "per compute-hour"}, {"unitAmount": "0.00001", "unitName": "per GB-hour"}]}


def test_find_offers_filters_and_sorts():
    m = FakeMarket([provider("a", "0.02", ["guest_firewall"], 4.5), provider("b", "0.01", [], 3.0), provider("c", "0.015", ["guest_firewall"], 4.9)])
    offers, located = marketplace.find_offers(m, "X", "Germany", "frankfurt", require_capabilities=["guest_firewall"])
    assert located == 3
    assert [o["provider_name"] for o in offers] == ["c", "a"]
    offers, located = marketplace.find_offers(m, "X", "Germany", "Frankfurt", sort="rating")
    assert [o["provider_name"] for o in offers] == ["c", "a", "b"]
    assert offers[0]["region_id"] == "region-c"
