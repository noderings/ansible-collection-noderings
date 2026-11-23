# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Firewall rule conversion and reconciliation shared by the firewall modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import ipaddress
import re

from ansible.module_utils.common.text.converters import to_text

from ansible_collections.noderings.cloud.plugins.module_utils.noderings import is_not_found, trim_enum

PROTOCOLS = [
    "tcp", "udp", "sctp", "ipv6", "icmp", "icmpv6", "esp", "ah", "ipsec", "gre", "ipip", "vxlan", "l2tp", "geneve", "any",
    "igmp", "ggp", "ipencap", "st", "egp", "igp", "pup", "hmp", "xns_idp", "rdp", "iso_tp4", "dccp", "xtp", "ddp", "idpr_cmtp",
    "ipv6_route", "ipv6_frag", "idrp", "rsvp", "skip", "ipv6_icmp", "ipv6_nonxt", "ipv6_opts", "vmtp", "eigrp", "ospf", "ax_25",
    "etherip", "encap", "pim", "ipcomp", "vrrp", "isis", "fc", "mobility_header", "udplite", "mpls_in_ip", "hip", "shim6", "wesp", "rohc",
]
PORT_PROTOCOLS = ["tcp", "udp", "sctp", "dccp", "udplite"]
MAX_RULES = 50
_PORTS_RE = re.compile(r"^(\d{1,5})(?:-(\d{1,5}))?$")

ENDPOINT_SPEC = dict(
    cidrs=dict(type="list", elements="str", default=[]),
    address_group_ids=dict(type="list", elements="str", default=[]),
    address_groups=dict(type="list", elements="str", default=[]),
    vm_tags=dict(type="list", elements="str", default=[]),
)

RULE_SPEC = dict(
    direction=dict(type="str", required=True, choices=["ingress", "egress"]),
    action=dict(type="str", required=True, choices=["accept", "drop"]),
    protocol=dict(type="str", default="tcp"),
    source=dict(type="dict", options=ENDPOINT_SPEC),
    destination=dict(type="dict", options=ENDPOINT_SPEC),
    source_ports=dict(type="str"),
    destination_ports=dict(type="str"),
)


def parse_prefix(value):
    """'10.0.0.0/8' or '10.0.0.1' -> ip_network (strict=False keeps host bits out)."""
    return ipaddress.ip_network(to_text(value).strip(), strict=False)


def prefixes_to_api(cidrs):
    out = []
    for c in cidrs:
        net = parse_prefix(c)
        out.append({"ip": str(net.network_address), "prefix": net.prefixlen})
    return out


def prefixes_from_api(prefixes):
    return ["%s/%s" % (p.get("ip"), int(p.get("prefix") or 0)) for p in prefixes or []]


def canonical_cidr(c):
    try:
        return str(parse_prefix(c))
    except ValueError:
        return to_text(c).strip().lower()


def validate_rule(rule, index):
    """Return an error message for one rule, or None."""
    where = "rule %d" % index
    if (rule.get("protocol") or "tcp") not in PROTOCOLS:
        return "%s: unknown protocol %r; use one of %s" % (where, rule.get("protocol"), ", ".join(PROTOCOLS))
    src, dst = rule.get("source") or {}, rule.get("destination") or {}

    def count(e):
        return sum(len(e.get(k) or []) for k in ("cidrs", "address_group_ids", "address_groups", "vm_tags"))

    if not count(src) and not count(dst):
        return ("%s needs a source or destination. To match any IPv4 address use cidrs: ['0.0.0.0/0']; "
                "for IPv6 add a second rule with ['::/0']." % where)
    for side, e in (("source", src), ("destination", dst)):
        cidrs = e.get("cidrs") or []
        for c in cidrs:
            try:
                parse_prefix(c)
            except ValueError:
                return "%s %s: %r is not an IP address or CIDR" % (where, side, c)
        anys = [c for c in cidrs if parse_prefix(c).prefixlen == 0]
        if anys and count(e) > 1:
            return ("%s %s: %s matches every address, so it must be the only entry on that side. "
                    "Write two rules to match both IPv4 and IPv6." % (where, side, " and ".join(anys)))
    for name in ("source_ports", "destination_ports"):
        v = rule.get(name)
        if v is None:
            continue
        if rule.get("protocol") not in PORT_PROTOCOLS:
            return "%s: protocol %s has no ports; %s only works with %s" % (where, rule.get("protocol"), name, ", ".join(PORT_PROTOCOLS))
        m = _PORTS_RE.match(to_text(v).strip())
        lo = int(m.group(1)) if m else 0
        hi = int(m.group(2) or lo) if m else 0
        if not m or not (1 <= lo <= hi <= 65535):
            return ("%s: %s %r must be one port such as 443 or one range such as 8000-8100. "
                    "Lists such as 80,443 are not supported; write one rule per port or range." % (where, name, v))
    return None


def _endpoint_to_api(e, group_ids_by_name):
    if not e:
        return None
    out = {}
    cidrs = [canonical_cidr(c) for c in e.get("cidrs") or []]
    if cidrs:
        out["ips"] = {"ips": sorted(cidrs)}
    ids = [i.lower() for i in e.get("address_group_ids") or []]
    for name in e.get("address_groups") or []:
        ids.append(group_ids_by_name[name].lower())
    if ids:
        out["addressGroupIds"] = {"addressGroupIds": sorted(set(ids))}
    tags = e.get("vm_tags") or []
    if tags:
        out["vmTags"] = {"tags": sorted(set(tags))}
    return out or None


def rule_to_api(rule, group_ids_by_name):
    body = {
        "action": "FIREWALL_ACTION_" + rule["action"].upper(),
        "protocol": "FIREWALL_PROTOCOL_" + (rule.get("protocol") or "tcp").upper(),
        "direction": "FIREWALL_DIRECTION_" + rule["direction"].upper(),
    }
    src = _endpoint_to_api(rule.get("source"), group_ids_by_name)
    dst = _endpoint_to_api(rule.get("destination"), group_ids_by_name)
    if src:
        body["source"] = src
    if dst:
        body["destination"] = dst
    if rule.get("source_ports"):
        body["sourcePorts"] = to_text(rule["source_ports"]).strip()
    if rule.get("destination_ports"):
        body["destinationPorts"] = to_text(rule["destination_ports"]).strip()
    return body


def _endpoint_key(e):
    if not e:
        return ""
    parts = []
    ips = sorted(canonical_cidr(c) for c in ((e.get("ips") or {}).get("ips") or []))
    if ips:
        parts.append("ips=" + ",".join(ips))
    groups = sorted(g.lower() for g in ((e.get("addressGroupIds") or {}).get("addressGroupIds") or []))
    if groups:
        parts.append("groups=" + ",".join(groups))
    tags = sorted((e.get("vmTags") or {}).get("tags") or [])
    if tags:
        parts.append("tags=" + ",".join(tags))
    return ";".join(parts)


def same_rule(a, b):
    """Compare two API rule bodies, ignoring list order."""
    return (
        a.get("action") == b.get("action")
        and a.get("protocol") == b.get("protocol")
        and a.get("direction") == b.get("direction")
        and (a.get("sourcePorts") or "") == (b.get("sourcePorts") or "")
        and (a.get("destinationPorts") or "") == (b.get("destinationPorts") or "")
        and _endpoint_key(a.get("source")) == _endpoint_key(b.get("source"))
        and _endpoint_key(a.get("destination")) == _endpoint_key(b.get("destination"))
    )


def _endpoint_view(e):
    e = e or {}
    out = {}
    ips = (e.get("ips") or {}).get("ips") or []
    if ips:
        out["cidrs"] = sorted(ips)
    groups = (e.get("addressGroupIds") or {}).get("addressGroupIds") or []
    if groups:
        out["address_group_ids"] = sorted(groups)
    tags = (e.get("vmTags") or {}).get("tags") or []
    if tags:
        out["vm_tags"] = sorted(tags)
    return out or None


def rule_view(r):
    """Ansible-facing view of an API rule (with or without id/position)."""
    body = r.get("rule", r)
    out = dict(
        direction=trim_enum(body.get("direction"), "FIREWALL_DIRECTION_"),
        action=trim_enum(body.get("action"), "FIREWALL_ACTION_"),
        protocol=trim_enum(body.get("protocol"), "FIREWALL_PROTOCOL_"),
        source=_endpoint_view(body.get("source")),
        destination=_endpoint_view(body.get("destination")),
        source_ports=body.get("sourcePorts") or None,
        destination_ports=body.get("destinationPorts") or None,
    )
    if "id" in r and "rule" in r:
        out["id"] = r.get("id")
        out["position"] = int(r.get("position") or 0)
    return out


def plan_rules(current, desired):
    """Decide what reconcile() would change, without calling the API.

    Returns True when the ruleset's rules differ from desired (contents or order).
    """
    if len(current) != len(desired):
        return True
    return any(not same_rule(c.get("rule") or {}, d) for c, d in zip(current, desired))


def reconcile(client, ruleset_id, desired):
    """Make the ruleset hold exactly `desired`, in order. Returns the final rules.

    Matching rules are kept (by body), changed ones are updated in place,
    missing ones are created and extra ones deleted; finally rules are moved
    into order. This keeps rule IDs stable where possible.
    """
    current = client.list_firewall_rules(ruleset_id)
    ids = [""] * len(desired)
    claimed = set()
    # Keep rules whose body already matches, preferring the same position.
    for i, d in enumerate(desired):
        if i < len(current) and current[i]["id"] not in claimed and same_rule(current[i].get("rule") or {}, d):
            ids[i] = current[i]["id"]
            claimed.add(ids[i])
    for i, d in enumerate(desired):
        if ids[i]:
            continue
        for c in current:
            if c["id"] not in claimed and same_rule(c.get("rule") or {}, d):
                ids[i] = c["id"]
                claimed.add(c["id"])
                break
    # Reuse leftover rules for changed bodies (update in place) before creating new ones.
    leftovers = [c for c in current if c["id"] not in claimed]
    for i, d in enumerate(desired):
        if ids[i] or not leftovers:
            continue
        c = leftovers.pop(0)
        client.update_firewall_rule(c["id"], d)
        ids[i] = c["id"]
        claimed.add(c["id"])
    for c in leftovers:
        try:
            client.delete_firewall_rule(c["id"])
        except Exception as e:  # pylint: disable=broad-except
            if not is_not_found(e):
                raise
    order = [c["id"] for c in current if c["id"] in claimed]
    # New rules land at position 0, so create bottom-up to keep their relative order.
    for i in range(len(desired) - 1, -1, -1):
        if ids[i]:
            continue
        created = client.create_firewall_rule(ruleset_id, desired[i])
        if not created or not created.get("id"):
            fresh = client.list_firewall_rules(ruleset_id)
            created = next((r for r in fresh if r["id"] not in claimed and same_rule(r.get("rule") or {}, desired[i])), None)
            if not created:
                raise RuntimeError("the API did not return the created firewall rule %d" % i)
        ids[i] = created["id"]
        claimed.add(ids[i])
        order.insert(0, ids[i])
    for i, rid in enumerate(ids):
        if order[i] == rid:
            continue
        client.move_firewall_rule(rid, order[i])
        order.remove(rid)
        order.insert(i, rid)
    final = client.list_firewall_rules(ruleset_id)
    if [r["id"] for r in final] != ids:
        raise RuntimeError("the ruleset's rules changed while they were being written (another tool or user edited it); run the task again")
    return final
