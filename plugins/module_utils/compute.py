# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Virtual machine helpers shared by the compute modules and the inventory plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    is_not_found,
    snake,
    trim_enum,
)

NONCE_TAG_PREFIX = "ansible-create-"


def power_state(vm):
    op = (vm or {}).get("operationStatus") or ""
    if op in ("OPERATION_STATUS_STARTED", "OPERATION_STATUS_RESTARTED"):
        return "running"
    if op == "OPERATION_STATUS_STOPPED":
        return "stopped"
    return trim_enum(op, "OPERATION_STATUS_") or "unknown"


def vm_view(vm):
    """The VM as modules return it: snake_case keys plus a few friendly fields."""
    if not vm:
        return {}
    out = snake(vm)
    out["power_state"] = power_state(vm)
    out["distro"] = trim_enum(vm.get("distro"), "DISTRO_")
    out["billing_type"] = trim_enum(vm.get("planBillingType"), "BILLING_TYPE_")
    out["provisioning_status"] = trim_enum(vm.get("crStatus"), "CR_STATUS_")
    out["tags"] = sorted(t for t in vm.get("tags") or [] if not t.startswith(NONCE_TAG_PREFIX))
    return out


def resolve_vm(nr, vm_id=None, hostname=None, required=True):
    """Find one VM by ID or by unique hostname. Returns None when absent and not required."""
    c = nr.client
    if vm_id:
        try:
            return c.get_virtual_machine(vm_id)
        except NodeRingsError as e:
            if is_not_found(e) and not required:
                return None
            nr.fail("reading virtual machine %s" % vm_id, e)
    vms = nr.call("listing virtual machines", c.list_virtual_machines)
    matches = [v for v in vms if v.get("hostname") == hostname]
    if len(matches) > 1:
        nr.module.fail_json(msg="%d virtual machines are named %s; pass the ID of the one you mean" % (len(matches), hostname),
                            ids=[v.get("id") for v in matches])
    if not matches:
        if required:
            nr.module.fail_json(msg="no virtual machine is named %s" % hostname)
        return None
    # List entries omit details such as add-on subscriptions; read the full VM.
    return nr.call("reading virtual machine %s" % hostname, c.get_virtual_machine, matches[0]["id"])


def translate_create_error(err):
    msg = str(err)
    low = msg.lower()
    if "payment method" in low:
        msg += ". Add a payment method to the organization in the NodeRings console. Paid plans, including usage-billed ones, need one."
    elif "runway" in low or "insufficient" in low:
        msg += ". Top up the organization's credit balance, or choose a cheaper plan."
    elif "no vm template" in low:
        msg += ". This provider has no image for the chosen distro in this region. Pick another distro, or another offer."
    elif "capacity" in low or "marketplace-ready node" in low:
        msg += ". The region is out of capacity for this plan. Try another provider or city."
    elif "plan" in low and "not found" in low:
        msg += ". The plan is not for sale (any more). Look up a current one with noderings.cloud.marketplace_offer_info."
    if isinstance(err, NodeRingsError) and err.is_quota():
        msg += ". The organization has reached its virtual machine quota. Delete unused VMs or ask NodeRings support to raise the limit."
    return msg
