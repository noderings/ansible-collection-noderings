# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.noderings.cloud.plugins.modules import virtual_machine
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.market_fakeapi import ACME, ACME_ID, market_routes


def vm_api(api, billing="BILLING_TYPE_USAGE", fail_first=None):
    vms = {}
    attempts = []

    @api.route("GET", "/v1/marketplace/plans/plan-1")
    def plan(q, b):
        return 200, {"planId": "plan-1", "billingType": billing}

    @api.route("GET", "/v1/ssh-keys")
    def keys(q, b):
        return 200, {"sshKeys": [{"id": "key-1", "name": "laptop"}]}

    @api.route("POST", "/v1/virtual-machines")
    def create(q, b):
        attempts.append(b)
        vm = dict(id="vm-1", hostname=b["hostname"], tags=b.get("tags", []), crStatus="CR_STATUS_APPLIED",
                  operationStatus="OPERATION_STATUS_STARTED", ipv4="203.0.113.10", planId=b["planId"], distro=b.get("distro"))
        vms[vm["id"]] = vm
        if fail_first and len(attempts) == 1:
            return fail_first, {"message": "gateway timeout"}
        return 200, {"virtualMachine": vm}

    @api.route("GET", "/v1/virtual-machines")
    def lst(q, b):
        return 200, {"virtualMachines": list(vms.values())}

    @api.route("GET", "/v1/virtual-machines/([^/:]+)")
    def get(q, b, vid):
        if vid not in vms:
            return 404, {"code": 5}
        return 200, vms[vid]

    @api.route("PATCH", "/v1/virtual-machines/([^/:]+)")
    def tags(q, b, vid):
        vm = vms[vid]
        vm["tags"] = sorted((set(vm["tags"]) | set(b["addTags"])) - set(b["removeTags"]))
        return 200, vm

    @api.route("POST", "/v1/virtual-machines/([^/:]+):stop")
    def stop(q, b, vid):
        vms[vid]["operationStatus"] = "OPERATION_STATUS_STOPPED"
        return 200, vms[vid]

    @api.route("DELETE", "/v1/virtual-machines/([^/:]+)")
    def delete(q, b, vid):
        vms.pop(vid)
        return 200, {}

    return vms, attempts


ORDER = dict(hostname="web-1", plan_id="plan-1", region_id="region-1", distro="ubuntu_24_04", ssh_keys=["laptop"], tags=["web"])


def test_vm_order_tags_power_delete(api, run):
    vms, attempts = vm_api(api)
    r = run(virtual_machine, ORDER)
    assert r["changed"] and r["virtual_machine"]["power_state"] == "running"
    assert attempts[0]["sshKeyIds"] == ["key-1"] and attempts[0]["distro"] == "DISTRO_UBUNTU_24_04" and attempts[0]["idempotencyKey"]
    assert not run(virtual_machine, ORDER)["changed"]
    r = run(virtual_machine, dict(hostname="web-1", tags=["db"], state="stopped"))
    assert r["changed"] and r["virtual_machine"]["tags"] == ["db"] and r["virtual_machine"]["power_state"] == "stopped"
    assert run(virtual_machine, dict(hostname="web-1", state="absent"))["changed"]
    assert vms == {}


def test_vm_free_plan_recovers_lost_response_by_tag(api, run):
    vms, attempts = vm_api(api, billing="BILLING_TYPE_FREE", fail_first=504)
    r = run(virtual_machine, ORDER)
    assert r["changed"] and not r.get("failed")
    assert len(attempts) == 1  # found by its nonce tag instead of ordering again
    assert r["virtual_machine"]["tags"] == ["web"]
    assert vms["vm-1"]["tags"] == ["web"]  # the temporary tag was removed


def test_vm_check_mode_and_missing_offer_args(api, run):
    vm_api(api)
    r = run(virtual_machine, ORDER, check_mode=True)
    assert r["changed"] and api.writes() == []
    r = run(virtual_machine, dict(hostname="web-2"))
    assert r["failed"] and "plan_code" in r["msg"]


BY_CODE = dict(hostname="web-1", plan_code="SC-GC-1C-1G-20", country="United States", city="Ashburn", billing_type="usage",
               distro="ubuntu_24_04", ssh_keys=["laptop"])


def market_api(api, extra=()):
    vm_api(api)

    @api.route("GET", "/v1/marketplace/plans/([^/]+)")
    def plan(q, b, plan_id):
        return 200, {"planId": plan_id, "billingType": "BILLING_TYPE_USAGE"}

    market_routes(api, extra=extra)


def ordered(api):
    return [b for m, p, q, b in api.calls if m == "POST" and p == "/v1/virtual-machines"]


@pytest.mark.parametrize("provider", [ACME_ID, "acme-hosting", "Acme Hosting", "  acme HOSTING "])
def test_vm_orders_from_the_named_provider(api, run, provider):
    market_api(api)
    r = run(virtual_machine, dict(BY_CODE, provider=provider))
    assert r["changed"] and not r.get("failed"), r
    assert ordered(api)[0]["planId"] == "plan-acme" and ordered(api)[0]["regionId"] == "region-acme"
    assert r["offer"]["provider_name"] == "Acme Hosting"


def test_vm_without_a_provider_takes_the_cheapest(api, run):
    market_api(api)
    r = run(virtual_machine, BY_CODE)
    assert r["changed"] and ordered(api)[0]["planId"] == "plan-cheap"


def test_vm_fails_for_an_unknown_provider(api, run):
    market_api(api)
    r = run(virtual_machine, dict(BY_CODE, provider="Nobody Hosting"))
    assert r["failed"] and "from provider Nobody Hosting" in r["msg"]
    assert ordered(api) == []


def test_vm_refuses_a_provider_name_two_providers_share(api, run):
    market_api(api, extra=[dict(ACME, organizationId="66666666-6666-6666-6666-666666666666")])
    r = run(virtual_machine, dict(BY_CODE, provider="acme hosting"))
    assert r["failed"] and "more than one provider is named acme hosting; give its provider ID or storefront slug instead" in r["msg"]
    assert ordered(api) == []


def test_vm_provider_excludes_provider_id_and_storefront_slug(api, run):
    market_api(api)
    for other in (dict(provider_id=ACME_ID), dict(storefront_slug="acme-hosting")):
        r = run(virtual_machine, dict(BY_CODE, provider="Acme Hosting", **other))
        assert r["failed"] and "mutually exclusive" in r["msg"]
    assert ordered(api) == []
