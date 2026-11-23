# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.modules import dns_record, secret, ssh_key, virtual_machine

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


def test_ssh_key_ignores_comment_and_replaces_on_change(api, run):
    keys = []

    @api.route("GET", "/v1/ssh-keys")
    def lst(q, b):
        return 200, {"sshKeys": keys}

    @api.route("POST", "/v1/ssh-keys")
    def create(q, b):
        keys.append({"id": "k%d" % len(keys), "name": b["name"], "publicKey": b["publicKey"]})
        return 200, {"sshKey": keys[-1]}

    @api.route("DELETE", "/v1/ssh-keys/([^/]+)")
    def delete(q, b, kid):
        keys[:] = [k for k in keys if k["id"] != kid]
        return 200, {}

    assert run(ssh_key, dict(name="me", public_key="ssh-ed25519 AAAA me@a"))["changed"]
    assert not run(ssh_key, dict(name="me", public_key="ssh-ed25519 AAAA other\n"))["changed"]
    r = run(ssh_key, dict(name="me", public_key="ssh-ed25519 BBBB me@a"))
    assert r["changed"] and len(keys) == 1 and keys[0]["publicKey"].startswith("ssh-ed25519 BBBB")


def test_secret_update_value(api, run):
    items = []

    @api.route("GET", "/v1/secrets")
    def lst(q, b):
        return 200, {"secrets": items}

    @api.route("POST", "/v1/secrets")
    def create(q, b):
        items.append({"id": "s1", "key": b["key"].lower()})
        return 200, {"secret": items[-1]}

    @api.route("PATCH", "/v1/secrets/s1")
    def update(q, b):
        return 200, {}

    assert run(secret, dict(key="API_KEY", value="x"))["changed"]
    assert not run(secret, dict(key="API_KEY", value="x", update_value="on_create"))["changed"]
    r = run(secret, dict(key="API_KEY", value="s3cr3t-value"))
    assert r["changed"] and "s3cr3t-value" not in str(r)


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
