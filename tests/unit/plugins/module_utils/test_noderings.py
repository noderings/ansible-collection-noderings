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

from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsClient,
    NodeRingsError,
    TimeoutError_,
    Waiter,
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
