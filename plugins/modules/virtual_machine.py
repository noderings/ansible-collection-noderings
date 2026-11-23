#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: virtual_machine
short_description: Order and manage NodeRings virtual machines
version_added: 0.1.0
description:
  - Orders a virtual machine from a hosting provider on the NodeRings marketplace, keeps its tags,
    firewall and power state as configured, reinstalls it on request, and deletes it.
  - Choose what to order either with O(plan_id) and O(region_id), or let the module pick an offer
    from O(plan_code), O(country) and O(city) (see M(noderings.cloud.marketplace_offer_info)).
  - Plan, region and offer options are only used when the VM is ordered. An existing VM is never moved
    to another offer, so a cheaper offer appearing later does not replace your server.
  - VMs are matched by O(hostname), or by O(id) when given.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
  - noderings.cloud.noderings.WAIT
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
options:
  hostname:
    description:
      - Hostname of the VM. Used to find an existing VM, so keep it unique within the organization.
      - Required unless O(id) is given.
    type: str
  id:
    description:
      - ID of an existing VM. Takes precedence over O(hostname) for finding the VM.
    type: str
  state:
    description:
      - V(present) orders the VM if needed and leaves its power state alone.
      - V(running) and V(stopped) also start or stop it.
      - V(restarted) stops and starts it.
      - V(reinstalled) reinstalls it from O(distro) or O(instant_app). This erases the disk every time it runs.
      - V(absent) deletes it. Billing stops.
    type: str
    choices: [present, running, stopped, restarted, reinstalled, absent]
    default: present
  plan_id:
    description:
      - Plan to order. Use together with O(region_id). Mutually exclusive with O(plan_code).
    type: str
  region_id:
    description:
      - Region of O(plan_id).
    type: str
  plan_code:
    description:
      - Marketplace plan code, for example C(SC-GC-1C-1G-20). The module picks an offer for this code
        in O(country) and O(city). See M(noderings.cloud.marketplace_plan_info).
    type: str
  country:
    description:
      - Country of the offer, for example C(Germany). Required with O(plan_code).
    type: str
  city:
    description:
      - City of the offer, for example C(Frankfurt). Required with O(plan_code).
    type: str
  billing_type:
    description:
      - V(usage) (billed hourly from prepaid credit), V(subscription) (monthly, charged to the card) or V(free).
      - Strongly recommended with O(plan_code); without it each provider offers one plan of its choice.
    type: str
    choices: [usage, subscription, free]
  provider_id:
    description:
      - Only consider offers from this hosting provider.
    type: str
  storefront_slug:
    description:
      - Only consider offers from the provider with this public storefront.
    type: str
  require_capabilities:
    description:
      - Only consider providers that support all of these, for example C(guest_firewall), C(snapshots),
        C(on_demand_backup) or C(instant_apps).
      - C(guest_firewall) is added automatically when O(firewall_ruleset) is set.
    type: list
    elements: str
    default: []
  require_ipv6:
    description:
      - Only consider offers with IPv6 in the city.
    type: bool
    default: false
  sort:
    description:
      - How to choose between offers. V(price) picks the cheapest compute price, V(rating) the best-rated provider.
    type: str
    choices: [price, rating]
    default: price
  distro:
    description:
      - Operating system, for example C(ubuntu_24_04) or C(debian_12). See M(noderings.cloud.distro_info).
      - Defaults to the provider's default distro, or the instant app's distro.
      - For an existing VM a different value only takes effect with O(allow_reinstall=true) or O(state=reinstalled).
    type: str
  instant_app:
    description:
      - Slug of a one-click application to install, for example C(wordpress). See M(noderings.cloud.instant_app_info).
    type: str
  instant_app_variables:
    description:
      - Settings for the instant app.
    type: dict
  ssh_keys:
    description:
      - Names or IDs of SSH keys to install for root. See M(noderings.cloud.ssh_key).
      - Only used when the VM is ordered or reinstalled.
    type: list
    elements: str
    default: []
  password:
    description:
      - Root password. Only used when the VM is ordered or reinstalled. Prefer O(ssh_keys).
    type: str
  coupon_code:
    description:
      - Promotion code applied to the order.
    type: str
  tags:
    description:
      - Tags. Firewall rules can match VMs by tag.
      - Leave unset to not manage tags.
    type: list
    elements: str
  purge_tags:
    description:
      - Remove tags that are not in O(tags). With V(false), O(tags) are only added.
    type: bool
    default: true
  firewall_ruleset:
    description:
      - Name or ID of the firewall ruleset to attach. An empty string detaches the current one.
      - Leave unset to not manage the firewall. The provider must support C(guest_firewall).
    type: str
  allow_reinstall:
    description:
      - Reinstall an existing VM when O(distro) or O(instant_app) differs from what it runs. This erases the disk.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Order a small hourly server in Ashburn
  noderings.cloud.virtual_machine:
    hostname: web-1
    plan_code: SC-GC-1C-1G-20
    country: United States
    city: Ashburn
    billing_type: usage
    distro: ubuntu_24_04
    ssh_keys: [laptop]
    tags: [web, prod]
    firewall_ruleset: web
    state: running
  register: vm

- name: Wait for SSH
  ansible.builtin.wait_for:
    host: "{{ vm.virtual_machine.ipv4 }}"
    port: 22

- name: Stop it for the night
  noderings.cloud.virtual_machine:
    hostname: web-1
    state: stopped

- name: Delete it
  noderings.cloud.virtual_machine:
    hostname: web-1
    state: absent
"""

RETURN = r"""
virtual_machine:
  description: The VM. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 2f6e0d1c-0000-4b4b-8c8c-0123456789ab
    hostname: web-1
    ipv4: 203.0.113.10
    ipv6: 2001:db8::10
    power_state: running
    provisioning_status: applied
    distro: ubuntu_24_04
    plan_code: SC-GC-1C-1G-20
    plan_id: 7f3a9c1e-0000-0000-0000-000000000000
    region_id: 2b8d4e6f-0000-0000-0000-000000000000
    region_city: Ashburn
    region_country: United States
    provider_name: Example Hosting
    billing_type: usage
    cpu: 1
    memory: 1
    storage: 20
    tags: [prod, web]
    firewall_ruleset_id: 7a6b5c4d-1111-2222-3333-444455556666
    capabilities: [guest_firewall, snapshots]
offer:
  description: The offer that was ordered, when the module chose one from O(plan_code).
  returned: when a VM was ordered from O(plan_code)
  type: dict
"""

import time

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import (
    NONCE_TAG_PREFIX,
    power_state,
    resolve_vm,
    translate_create_error,
    vm_view,
)
from ansible_collections.noderings.cloud.plugins.module_utils.marketplace import (
    NoOfferError,
    find_offers,
    no_offer_message,
    offer_view,
)
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    NodeRingsModule,
    TimeoutError_,
    Waiter,
    is_ambiguous,
    is_not_found,
    new_uuid,
    noderings_argument_spec,
    trim_enum,
)


class VirtualMachine(NodeRingsModule):

    def __init__(self, module):
        super(VirtualMachine, self).__init__(module)
        self.p = module.params
        self.waiter = Waiter(self.p["wait_timeout"])
        self.warnings = []

    # -- lookups ---------------------------------------------------------------------

    def ssh_key_ids(self):
        if not self.p["ssh_keys"]:
            return []
        keys = self.call("listing SSH keys", self.client.list_ssh_keys)
        by_name = dict((k.get("name"), k.get("id")) for k in keys)
        ids = set(k.get("id") for k in keys)
        out = []
        for ref in self.p["ssh_keys"]:
            if ref in ids:
                out.append(ref)
            elif ref in by_name:
                out.append(by_name[ref])
            else:
                self.module.fail_json(msg="SSH key %s does not exist; upload it with noderings.cloud.ssh_key" % ref)
        return sorted(set(out))

    def ruleset_id(self):
        ref = self.p["firewall_ruleset"]
        if ref is None or ref == "":
            return ref
        sets = self.call("listing firewall rulesets", self.client.list_firewall_rulesets)
        for s in sets:
            if s.get("id") == ref or s.get("name") == ref:
                return s["id"]
        self.module.fail_json(msg="firewall ruleset %s does not exist; create it with noderings.cloud.firewall_ruleset" % ref)

    def instant_app(self):
        slug = self.p["instant_app"]
        if not slug:
            return None
        try:
            return self.client.get_instant_app_by_slug(slug)
        except NodeRingsError as e:
            if is_not_found(e):
                self.module.fail_json(msg="instant app %s does not exist; list apps with noderings.cloud.instant_app_info" % slug)
            self.fail("reading instant app %s" % slug, e)

    def choose_offer(self):
        p = self.p
        if p["plan_id"]:
            return p["plan_id"], p["region_id"], None
        caps = list(p["require_capabilities"] or [])
        if p["firewall_ruleset"] and "guest_firewall" not in caps:
            caps.append("guest_firewall")
        try:
            offers, located = find_offers(
                self.client, p["plan_code"], p["country"], p["city"], billing_type=p["billing_type"],
                provider_id=p["provider_id"], storefront_slug=p["storefront_slug"], require_capabilities=caps,
                require_ipv6=p["require_ipv6"], sort=p["sort"])
        except (NodeRingsError, NoOfferError) as e:
            self.fail("looking up offers for %s" % p["plan_code"], e)
        if not offers:
            self.module.fail_json(msg=no_offer_message(p["plan_code"], p["country"], p["city"], p["billing_type"], located))
        best = offers[0]
        return best["plan_id"], best["region_id"], offer_view(best)

    # -- waiting ---------------------------------------------------------------------

    def wait_provisioned(self, vm_id):
        last = {}

        def check():
            vm = self.client.get_virtual_machine(vm_id)
            last["vm"] = vm
            status = vm.get("crStatus")
            if status == "CR_STATUS_APPLIED":
                return True, vm
            if status == "CR_STATUS_FAILED":
                raise RuntimeError("provisioning of virtual machine %s failed. The API does not report why; delete it and try "
                                   "another offer, or contact the provider" % vm_id)
            return False, None

        try:
            return self.waiter.wait("virtual machine %s to be provisioned" % vm_id, check)
        except (NodeRingsError, RuntimeError, TimeoutError_) as e:
            self.module.fail_json(msg=str(e), changed=True, virtual_machine=vm_view(last.get("vm")))

    def wait_idle(self, vm_id, check_vm, what):
        def check():
            vm = self.client.get_virtual_machine(vm_id)
            return (check_vm(vm) and vm.get("crStatus") != "CR_STATUS_PROCESSING"), vm

        return self.call("waiting for %s" % what, self.waiter.wait, what, check)

    def wait_settled(self, vm_id):
        """Wait while the VM is in a transitional power state (created, reinstalling)."""
        return self.wait_idle(vm_id, lambda vm: power_state(vm) in ("running", "stopped"),
                              "the virtual machine to finish booting")

    def set_power(self, vm_id, want):
        action = "stop" if want == "stopped" else "start"
        self.call("%s virtual machine" % ("stopping" if want == "stopped" else "starting"),
                  self.waiter.retry_busy, lambda: self.client.vm_action(vm_id, action))
        if self.p["wait"]:
            return self.wait_idle(vm_id, lambda vm: power_state(vm) == want, "the virtual machine to be %s" % want)
        return None

    # -- create ----------------------------------------------------------------------

    def find_by_tag(self, tag):
        for vm in self.client.list_virtual_machines():
            if tag in (vm.get("tags") or []):
                return vm
        return None

    def create(self):
        p = self.p
        plan_id, region_id, offer = self.choose_offer()
        app = self.instant_app()
        ruleset = self.ruleset_id()
        body = dict(hostname=p["hostname"], planId=plan_id, regionId=region_id, idempotencyKey=new_uuid())
        if p["distro"]:
            body["distro"] = "DISTRO_" + p["distro"].upper()
        keys = self.ssh_key_ids()
        if keys:
            body["sshKeyIds"] = keys
        if p["password"]:
            body["password"] = p["password"]
        if app:
            body["instantAppId"] = app.get("id")
        if p["instant_app_variables"]:
            body["instantAppVariables"] = dict((k, str(v)) for k, v in p["instant_app_variables"].items())
        if p["coupon_code"]:
            body["coupon"] = {"code": p["coupon_code"]}
        tags = sorted(set(p["tags"] or []))
        if self.module.check_mode:
            after = dict(hostname=p["hostname"], plan_id=plan_id, region_id=region_id, tags=tags,
                         distro=p["distro"] or "", power_state="stopped" if p["state"] == "stopped" else "running")
            self.module.exit_json(changed=True, virtual_machine=after, offer=offer, diff=dict(before={}, after=after))

        # Free plans ignore the idempotency key, so a retry after a lost response could order
        # a second VM. Tag the order with a nonce so the VM can be found instead.
        nonce = ""
        try:
            plan = self.client.get_marketplace_plan(plan_id)
            free = plan.get("billingType") == "BILLING_TYPE_FREE"
        except NodeRingsError:
            free = True
        if free:
            nonce = NONCE_TAG_PREFIX + new_uuid()
            tags = tags + [nonce]
        if tags:
            body["tags"] = tags

        vm, last_err, new_key = None, None, False
        for attempt in range(6):
            try:
                vm = self.client.create_virtual_machine(body)
                break
            except NodeRingsError as e:
                last_err = e
                if e.code == 9 and "new idempotency key" in e.message.lower() and not new_key:
                    new_key = True
                    body["idempotencyKey"] = new_uuid()
                    continue
                if not is_ambiguous(e):
                    self.module.fail_json(msg="ordering virtual machine %s: %s" % (p["hostname"], translate_create_error(e)))
            except (IOError, OSError) as e:
                last_err = e
            if nonce:
                found = self.find_by_tag(nonce)
                if found:
                    vm = found
                    break
            time.sleep(min(2 * (attempt + 1), 10))
        else:
            self.module.fail_json(msg="ordering virtual machine %s: %s. The order may or may not have been placed; "
                                      "check the console before running again" % (p["hostname"], last_err))
        if (not vm or not vm.get("id")) and nonce:
            vm = self.find_by_tag(nonce)
        if not vm or not vm.get("id"):
            self.module.fail_json(msg="the API accepted the order for %s but did not return the new virtual machine; "
                                      "check the console before running again" % p["hostname"], changed=True)
        vm_id = vm["id"]
        if p["wait"] or ruleset or nonce or p["state"] == "stopped":
            vm = self.wait_provisioned(vm_id)
            # The VM reads CREATED until the platform has booted it, then STARTED.
            vm = self.wait_settled(vm_id)
        if nonce:
            try:
                self.client.update_virtual_machine_tags(vm_id, remove=[nonce])
            except NodeRingsError as e:
                self.warnings.append("could not remove the temporary tag %s: %s" % (nonce, e))
        if ruleset:
            self.call("attaching firewall", self.waiter.retry_busy, lambda: self.client.vm_action(vm_id, "attach-firewall", {"rulesetId": ruleset}))
            if p["wait"]:
                self.wait_idle(vm_id, lambda vm: vm.get("firewallRulesetId") == ruleset, "the firewall to be applied")
        if p["state"] == "stopped":
            self.set_power(vm_id, "stopped")
        vm = self.call("reading virtual machine", self.client.get_virtual_machine, vm_id)
        return vm, offer

    # -- update ----------------------------------------------------------------------

    def update(self, vm):
        p = self.p
        vm_id = vm["id"]
        changed = False
        check = self.module.check_mode
        after = vm_view(vm)

        if p["tags"] is not None:
            have = set(t for t in vm.get("tags") or [] if not t.startswith(NONCE_TAG_PREFIX))
            want = set(p["tags"])
            add = sorted(want - have)
            remove = sorted(have - want) if p["purge_tags"] else []
            if add or remove:
                changed = True
                after["tags"] = sorted((have | want) - set(remove))
                if not check:
                    self.call("updating tags", self.waiter.retry_busy, lambda: self.client.update_virtual_machine_tags(vm_id, add, remove))

        if p["firewall_ruleset"] is not None:
            want_rs = self.ruleset_id()
            have_rs = vm.get("firewallRulesetId") or ""
            if want_rs != have_rs:
                if want_rs and "guest_firewall" not in (vm.get("capabilities") or []):
                    self.module.fail_json(msg="the provider of %s does not support guest_firewall, so no firewall can be attached" % vm.get("hostname"))
                changed = True
                after["firewall_ruleset_id"] = want_rs
                if not check:
                    if have_rs:
                        self.call("detaching firewall", self.waiter.retry_busy,
                                  lambda: self.client.vm_action(vm_id, "detach-firewall", {"rulesetId": have_rs}))
                    if want_rs:
                        self.call("attaching firewall", self.waiter.retry_busy,
                                  lambda: self.client.vm_action(vm_id, "attach-firewall", {"rulesetId": want_rs}))
                    if p["wait"]:
                        self.wait_idle(vm_id, lambda v: (v.get("firewallRulesetId") or "") == want_rs, "the firewall change to be applied")

        reinstall = p["state"] == "reinstalled"
        if not reinstall and (p["distro"] or p["instant_app"]):
            have_distro = trim_enum(vm.get("distro"), "DISTRO_")
            have_app = vm.get("instantAppSlug") or ""
            differs = (p["distro"] and p["distro"].lower() != have_distro) or (p["instant_app"] and p["instant_app"] != have_app)
            if differs and p["allow_reinstall"]:
                reinstall = True
            elif differs:
                self.warnings.append("%s runs %s%s; set allow_reinstall=true to reinstall it (this erases the disk)" % (
                    vm.get("hostname"), have_distro, (" with " + have_app) if have_app else ""))
        if reinstall:
            changed = True
            if not check:
                self.reinstall(vm_id)

        if p["plan_id"] and p["plan_id"] != vm.get("planId"):
            self.warnings.append("%s stays on plan %s; plan and offer options only apply when a VM is ordered" % (vm.get("hostname"), vm.get("planId")))

        if p["state"] in ("running", "stopped"):
            current = vm if (check or not changed) else self.client.get_virtual_machine(vm_id)
            if not check and power_state(current) not in ("running", "stopped"):
                current = self.wait_settled(vm_id)
            if power_state(current) != p["state"]:
                changed = True
                after["power_state"] = p["state"]
                if not check:
                    self.set_power(vm_id, p["state"])
        elif p["state"] == "restarted":
            changed = True
            if not check:
                if power_state(self.client.get_virtual_machine(vm_id)) != "stopped":
                    self.set_power(vm_id, "stopped")
                self.set_power(vm_id, "running")

        if changed and not check:
            after = vm_view(self.call("reading virtual machine", self.client.get_virtual_machine, vm_id))
        return changed, after

    def reinstall(self, vm_id):
        p = self.p
        app = self.instant_app()
        body = dict(hostname=p["hostname"] or "")
        if p["distro"] and not app:
            body["distro"] = "DISTRO_" + p["distro"].upper()
        keys = self.ssh_key_ids()
        if keys:
            body["sshKeyIds"] = keys
        if p["password"]:
            body["password"] = p["password"]
        if app:
            body["instantAppId"] = app.get("id")
        if p["instant_app_variables"]:
            body["instantAppVariables"] = dict((k, str(v)) for k, v in p["instant_app_variables"].items())
        self.call("reinstalling virtual machine", self.waiter.retry_busy, lambda: self.client.vm_action(vm_id, "reinstall", body))
        if not p["wait"]:
            return

        def check():
            vm = self.client.get_virtual_machine(vm_id)
            status = vm.get("reinstallStatus")
            if status == "REINSTALL_STATUS_FAILED":
                raise RuntimeError("the reinstall of virtual machine %s failed; the API does not report why" % vm_id)
            return status == "REINSTALL_STATUS_COMPLETED" and vm.get("crStatus") != "CR_STATUS_PROCESSING", vm

        # The status may still read COMPLETED from an earlier reinstall for a moment.
        time.sleep(3)
        self.call("waiting for the reinstall", self.waiter.wait, "the reinstall to finish", check)

    def delete(self, vm):
        vm_id = vm["id"]
        try:
            self.waiter.retry_busy(lambda: self.client.delete_virtual_machine(vm_id))
        except NodeRingsError as e:
            if not is_not_found(e):
                self.fail("deleting virtual machine %s" % vm.get("hostname"), e)
        except TimeoutError_ as e:
            self.fail("deleting virtual machine %s" % vm.get("hostname"), e)
        if not self.p["wait"]:
            return

        def check():
            try:
                self.client.get_virtual_machine(vm_id)
            except NodeRingsError as e:
                if is_not_found(e):
                    return True, None
                raise
            return False, None

        self.call("waiting for the deletion", self.waiter.wait, "virtual machine %s to be deleted" % vm.get("hostname"), check)

    def run(self):
        p = self.p
        m = self.module
        vm = resolve_vm(self, p["id"], p["hostname"], required=False)
        before = vm_view(vm)

        if p["state"] == "absent":
            if not vm:
                m.exit_json(changed=False, virtual_machine={})
            if not m.check_mode:
                self.delete(vm)
            m.exit_json(changed=True, virtual_machine={}, diff=dict(before=before, after={}))

        if not vm:
            if p["id"]:
                m.fail_json(msg="virtual machine %s does not exist" % p["id"])
            if not p["hostname"]:
                m.fail_json(msg="hostname is required to order a virtual machine")
            if not p["plan_id"] and not (p["plan_code"] and p["country"] and p["city"]):
                m.fail_json(msg="to order %s, set plan_id and region_id, or plan_code, country and city" % p["hostname"])
            if p["state"] in ("reinstalled", "restarted"):
                m.fail_json(msg="virtual machine %s does not exist, so it cannot be %s" % (p["hostname"], p["state"]))
            vm, offer = self.create()
            after = vm_view(vm)
            result = dict(changed=True, virtual_machine=after, diff=dict(before={}, after=after))
            if offer:
                result["offer"] = offer
            self.flush_warnings()
            m.exit_json(**result)

        changed, after = self.update(vm)
        self.flush_warnings()
        m.exit_json(changed=changed, virtual_machine=after, diff=dict(before=before, after=after))

    def flush_warnings(self):
        for w in self.warnings:
            self.module.warn(w)


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        hostname=dict(type="str"),
        id=dict(type="str"),
        state=dict(type="str", default="present", choices=["present", "running", "stopped", "restarted", "reinstalled", "absent"]),
        plan_id=dict(type="str"),
        region_id=dict(type="str"),
        plan_code=dict(type="str"),
        country=dict(type="str"),
        city=dict(type="str"),
        billing_type=dict(type="str", choices=["usage", "subscription", "free"]),
        provider_id=dict(type="str"),
        storefront_slug=dict(type="str"),
        require_capabilities=dict(type="list", elements="str", default=[]),
        require_ipv6=dict(type="bool", default=False),
        sort=dict(type="str", default="price", choices=["price", "rating"]),
        distro=dict(type="str"),
        instant_app=dict(type="str"),
        instant_app_variables=dict(type="dict"),
        ssh_keys=dict(type="list", elements="str", default=[], no_log=False),
        password=dict(type="str", no_log=True),
        coupon_code=dict(type="str"),
        tags=dict(type="list", elements="str"),
        purge_tags=dict(type="bool", default=True),
        firewall_ruleset=dict(type="str"),
        allow_reinstall=dict(type="bool", default=False),
        wait=dict(type="bool", default=True),
        wait_timeout=dict(type="int", default=1800),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[("hostname", "id")],
        mutually_exclusive=[("plan_id", "plan_code"), ("provider_id", "storefront_slug")],
        required_together=[("plan_id", "region_id"), ("plan_code", "country", "city")],
        supports_check_mode=True,
    )
    VirtualMachine(module).run()


if __name__ == "__main__":
    main()
