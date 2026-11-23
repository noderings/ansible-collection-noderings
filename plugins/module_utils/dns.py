# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""DNS name and record-value helpers shared by the DNS modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import ipaddress

from ansible.module_utils.common.text.converters import to_text

RECORD_TYPES = [
    "A", "AAAA", "ALIAS", "CAA", "CERT", "CNAME", "DNAME", "DS", "HINFO", "HTTPS",
    "LOC", "MX", "NAPTR", "NS", "OPENPGPKEY", "PTR", "RP", "SMIMEA", "SRV", "SSHFP",
    "SVCB", "TLSA", "TXT",
]
GEO_RECORD_TYPES = ["A", "AAAA", "CNAME", "NAPTR", "SRV"]
SINGLE_VALUE_TYPES = frozenset(["CNAME", "DNAME", "ALIAS"])


def normalize_zone_name(name):
    return (name or "").strip().lower().rstrip(".")


def relative_name(name, zone):
    """www.example.com. in example.com -> www; the apex -> @."""
    n = (name or "").strip().lower()
    z = normalize_zone_name(zone)
    if n in ("", "@"):
        return "@"
    n = n.rstrip(".")
    if z:
        if n == z:
            return "@"
        if n.endswith("." + z):
            n = n[: -len(z) - 1]
    return n


def validate_values(rrtype, values):
    """Return an error message, or None when the values are acceptable."""
    if not values:
        return "at least one record value is required"
    if rrtype in SINGLE_VALUE_TYPES and len(values) > 1:
        return "%s records take exactly one value" % rrtype
    for v in values:
        v = to_text(v)
        if not v.strip():
            return "record values must not be empty"
        if rrtype in ("A", "AAAA", "ALIAS"):
            try:
                ip = ipaddress.ip_address(v.strip())
            except ValueError:
                ip = None
            if rrtype == "A" and (ip is None or ip.version != 4):
                return "%r is not an IPv4 address" % v
            if rrtype == "AAAA" and (ip is None or ip.version != 6 or ip.ipv4_mapped):
                return "%r is not an IPv6 address" % v
            if rrtype == "ALIAS" and ip is not None:
                return "ALIAS must point to a hostname, not an address"
        if rrtype == "TXT" and len(v) > 4096:
            return "TXT values are limited to 4096 characters"
    return None


def _fqdn(h):
    h = (h or "").strip().lower()
    if h in ("", "."):
        return h
    return h.rstrip(".") + "."


def canonical(rrtype, v):
    """A comparable form of one value: the API may lowercase names or add trailing dots."""
    v = to_text(v).strip()
    if rrtype == "TXT":
        return v
    if rrtype in ("A", "AAAA"):
        try:
            return str(ipaddress.ip_address(v))
        except ValueError:
            return v.lower()
    if rrtype in ("CNAME", "DNAME", "ALIAS", "NS", "PTR"):
        return _fqdn(v)
    f = v.split()
    if rrtype == "MX" and len(f) == 2:
        return f[0] + " " + _fqdn(f[1])
    if rrtype == "SRV" and len(f) == 4:
        return " ".join(f[:3]) + " " + _fqdn(f[3])
    return " ".join(v.lower().split())


def same_values(rrtype, a, b):
    return sorted(canonical(rrtype, x) for x in a or []) == sorted(canonical(rrtype, x) for x in b or [])


def _utf8_start(b):
    return (b & 0xC0) != 0x80


def quote_txt(v):
    """Split a TXT value into 255-byte quoted strings, as the API expects."""
    raw = to_text(v).encode("utf-8")
    parts = []
    while len(raw) > 255:
        cut = 255
        while cut > 0 and not _utf8_start(raw[cut]):
            cut -= 1
        parts.append(raw[:cut])
        raw = raw[cut:]
    parts.append(raw)
    out = []
    for p in parts:
        s = p.decode("utf-8").replace("\\", "\\\\").replace('"', '\\"')
        out.append('"' + s + '"')
    return " ".join(out)


def unquote_txt(v):
    """Join the API's quoted TXT strings back into one value."""
    v = to_text(v).strip()
    if not v.startswith('"'):
        return v
    out = []
    inside = False
    i = 0
    while i < len(v):
        c = v[i]
        if c == '"':
            inside = not inside
        elif c == "\\" and inside and i + 1 < len(v):
            i += 1
            out.append(v[i])
        elif inside:
            out.append(c)
        i += 1
    return "".join(out)


def to_api(rrtype, v):
    return quote_txt(v) if rrtype == "TXT" else to_text(v).strip()


def from_api(rrtype, v):
    return unquote_txt(v) if rrtype == "TXT" else to_text(v).strip()


def find_zone(nr, zone=None, zone_id=None):
    """Resolve a zone by ID or name; fails the module when it does not exist."""
    zones = nr.call("listing DNS zones", nr.client.list_dns_zones)
    if zone_id:
        match = next((z for z in zones if z.get("id") == zone_id), None)
        what = zone_id
    else:
        name = normalize_zone_name(zone)
        match = next((z for z in zones if normalize_zone_name(z.get("name")) == name), None)
        what = name
    if not match:
        nr.module.fail_json(msg="DNS zone %s does not exist in this organization. Create it with noderings.cloud.dns_zone first." % what)
    return match
