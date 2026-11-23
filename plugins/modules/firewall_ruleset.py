#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: firewall_ruleset
short_description: Manage NodeRings firewall rulesets and their rules
version_added: 0.1.0
description:
  - A ruleset is an ordered list of firewall rules that can be attached to virtual machines
    (see O(noderings.cloud.virtual_machine#module:firewall_ruleset)).
  - When O(rules) is given, the ruleset is made to hold exactly those rules, in that order.
    Rules that already match are kept, so their IDs stay the same.
  - The firewall runs in the guest, so the VM's hosting provider must support C(guest_firewall).
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
  name:
    description:
      - Name of the ruleset. Unique within the organization.
    type: str
    required: true
  rules:
    description:
      - The rules, first evaluated first. At most 50.
      - Leave unset to not manage the rules. An empty list removes all rules.
    type: list
    elements: dict
    suboptions:
      direction:
        description: V(ingress) (traffic to the VM) or V(egress) (traffic from it).
        type: str
        required: true
        choices: [ingress, egress]
      action:
        description: What to do with matching traffic.
        type: str
        required: true
        choices: [accept, drop]
      protocol:
        description:
          - IP protocol in lower case, for example V(tcp), V(udp), V(icmp), V(ipv6_icmp) (ICMPv6) or V(any).
          - Any IANA protocol name the platform knows is accepted, such as V(gre), V(esp) or V(sctp).
        type: str
        default: tcp
      source:
        description:
          - Where the traffic comes from. A rule needs a O(rules[].source) or a O(rules[].destination).
        type: dict
        suboptions: &endpoint
          cidrs:
            description:
              - Addresses or prefixes. V(0.0.0.0/0) or V(::/0) match everything and must be alone.
            type: list
            elements: str
            default: []
          address_groups:
            description: Names of address groups (see M(noderings.cloud.firewall_address_group)).
            type: list
            elements: str
            default: []
          address_group_ids:
            description: IDs of address groups.
            type: list
            elements: str
            default: []
          vm_tags:
            description:
              - Match the addresses of your virtual machines that have any of these tags.
              - Each tag must be on at least one existing virtual machine when the rule is written,
                so create the VMs first. If no VM has the tag any more, the platform skips the rule.
            type: list
            elements: str
            default: []
      destination:
        description: Where the traffic goes.
        type: dict
        suboptions: *endpoint
      source_ports:
        description:
          - One port such as V(443) or one range such as V(8000-8100). Only for TCP, UDP, SCTP, DCCP and UDP-Lite.
        type: str
      destination_ports:
        description:
          - One port such as V(443) or one range such as V(8000-8100). Only for TCP, UDP, SCTP, DCCP and UDP-Lite.
        type: str
  state:
    description:
      - Whether the ruleset should exist.
    type: str
    choices: [present, absent]
    default: present
  force:
    description:
      - With O(state=absent), delete the ruleset even while it is attached to virtual machines.
        They are left without a firewall.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Web server firewall
  noderings.cloud.firewall_ruleset:
    name: web
    rules:
      - {direction: ingress, action: accept, protocol: tcp, destination_ports: "22", source: {address_groups: [office]}}
      - {direction: ingress, action: accept, protocol: tcp, destination_ports: "80", source: {cidrs: [0.0.0.0/0]}}
      - {direction: ingress, action: accept, protocol: tcp, destination_ports: "443", source: {cidrs: [0.0.0.0/0]}}
      - {direction: ingress, action: accept, protocol: tcp, destination_ports: "443", source: {cidrs: ["::/0"]}}
      - {direction: ingress, action: accept, protocol: icmp, source: {cidrs: [0.0.0.0/0]}}
      - {direction: ingress, action: drop, protocol: any, source: {cidrs: [0.0.0.0/0]}}
  register: fw

- name: Remove a ruleset
  noderings.cloud.firewall_ruleset:
    name: old
    state: absent
    force: true
"""

RETURN = r"""
ruleset:
  description: The ruleset with its rules. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 7a6b5c4d-1111-2222-3333-444455556666
    name: web
    attached_vm_count: 1
    attached_vm_hostnames: [web-1]
    rules:
      - id: 1a2b3c4d-0000-0000-0000-000000000001
        position: 0
        direction: ingress
        action: accept
        protocol: tcp
        source: {cidrs: [0.0.0.0/0]}
        destination: null
        source_ports: null
        destination_ports: "443"
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.firewall import (
    MAX_RULES,
    RULE_SPEC,
    plan_rules,
    reconcile,
    rule_to_api,
    rule_view,
    validate_rule,
)
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
)


def view(rs, rules):
    if not rs:
        return {}
    return dict(
        id=rs.get("id"),
        name=rs.get("name"),
        attached_vm_count=int_or_zero(rs.get("attachedVmCount")),
        attached_vm_hostnames=rs.get("attachedVmHostnames") or [],
        rules=[rule_view(r) for r in rules],
    )


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        rules=dict(type="list", elements="dict", options=RULE_SPEC),
        state=dict(type="str", default="present", choices=["present", "absent"]),
        force=dict(type="bool", default=False),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    name = p["name"]
    current = c.find_by_name(nr.call("listing rulesets", c.list_firewall_rulesets, name), name)
    current_rules = nr.call("listing rules", c.list_firewall_rules, current["id"]) if current else []
    before = view(current, current_rules)

    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, ruleset={})
        if not module.check_mode:
            try:
                c.delete_firewall_ruleset(current["id"], p["force"])
            except Exception as e:  # pylint: disable=broad-except
                hint = "" if p["force"] else " If it is attached to virtual machines, detach it first or set force=true."
                module.fail_json(msg="deleting ruleset %s: %s.%s" % (name, e, hint))
        module.exit_json(changed=True, ruleset={}, diff=dict(before=before, after={}))

    desired = None
    if p["rules"] is not None:
        if len(p["rules"]) > MAX_RULES:
            module.fail_json(msg="a ruleset holds at most %d rules; got %d" % (MAX_RULES, len(p["rules"])))
        for i, r in enumerate(p["rules"]):
            err = validate_rule(r, i)
            if err:
                module.fail_json(msg=err)
        group_names = set(n for r in p["rules"] for side in ("source", "destination") for n in ((r.get(side) or {}).get("address_groups") or []))
        ids_by_name = {}
        if group_names:
            groups = nr.call("listing address groups", c.list_firewall_address_groups)
            ids_by_name = dict((g.get("name"), g.get("id")) for g in groups)
            missing = sorted(group_names - set(ids_by_name))
            if missing:
                module.fail_json(msg="address group(s) %s do not exist; create them with noderings.cloud.firewall_address_group" % ", ".join(missing))
        desired = [rule_to_api(r, ids_by_name) for r in p["rules"]]

    changed = not current or (desired is not None and plan_rules(current_rules, desired))
    if not changed:
        module.exit_json(changed=False, ruleset=before)

    if module.check_mode:
        after = dict(before or dict(name=name, attached_vm_count=0, attached_vm_hostnames=[]))
        if desired is not None:
            after["rules"] = [rule_view(d) for d in desired]
        else:
            after.setdefault("rules", [])
        module.exit_json(changed=True, ruleset=after, diff=dict(before=before, after=after))

    if not current:
        current = nr.call("creating ruleset %s" % name, c.create_firewall_ruleset, name)
    if desired is not None:
        try:
            reconcile(c, current["id"], desired)
        except Exception as e:  # pylint: disable=broad-except
            hint = ""
            uses_tags = any((r.get(side) or {}).get("vm_tags") for r in p["rules"] for side in ("source", "destination"))
            if uses_tags and "address" in str(e).lower():
                hint = " Each vm_tags tag must be on at least one existing virtual machine when the rule is written."
            module.fail_json(msg="writing the rules of %s: %s.%s" % (name, e, hint))
    rs = nr.call("reading ruleset %s" % name, c.get_firewall_ruleset, current["id"])
    rules = nr.call("listing rules", c.list_firewall_rules, current["id"])
    after = view(rs, rules)
    module.exit_json(changed=True, ruleset=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
