#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: dns_zone
short_description: Manage NodeRings DNS zones and DNSSEC
version_added: 0.1.0
description:
  - Creates or deletes a hosted DNS zone, and turns DNSSEC signing on or off.
  - After creating a zone, point your domain's nameservers at the C(assigned_nameservers) of RV(zone) at your registrar.
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
      - The domain, for example C(example.com). A trailing dot and upper case are ignored.
    type: str
    required: true
  state:
    description:
      - Whether the zone should exist.
    type: str
    choices: [present, absent]
    default: present
  force:
    description:
      - With O(state=absent), delete the zone even while DNSSEC is active and the parent zone still publishes the DS record.
        That breaks resolution for validating resolvers until the DS is removed, so remove the DS at the registrar first.
      - Records in the zone are always deleted with it.
    type: bool
    default: false
  dnssec:
    description:
      - V(true) signs the zone, V(false) stops signing. Leave unset to not manage DNSSEC.
      - After turning it on, publish RV(dnssec.ds) at your registrar.
    type: bool
  dnssec_force_disable:
    description:
      - Stop signing even while the DS record is still published at the parent. This breaks resolution
        for validating resolvers until the DS is removed, so remove the DS at the registrar first.
    type: bool
    default: false
  check_delegation:
    description:
      - Ask the API to re-check whether the domain is delegated to NodeRings nameservers, and return the result.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Host example.com on NodeRings DNS with DNSSEC
  noderings.cloud.dns_zone:
    name: example.com
    dnssec: true
  register: zone

- name: Show what to set at the registrar
  ansible.builtin.debug:
    msg:
      - "Nameservers: {{ zone.zone.assigned_nameservers | join(', ') }}"
      - "DS record: {{ zone.dnssec.ds }}"

- name: Delete a zone and all its records
  noderings.cloud.dns_zone:
    name: old-example.com
    state: absent
"""

RETURN = r"""
zone:
  description: The zone. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 0f3c7b9e-1111-4c4c-8a8a-123456789abc
    name: example.com
    state: ZONE_STATE_ACTIVE
    assigned_nameservers: [ns1.example.net, ns2.example.net]
    delegation_ok: false
    dnssec_mode: DNSSEC_MODE_UNSIGNED
dnssec:
  description: DNSSEC state of the zone. Returned when O(dnssec) is set.
  returned: when O(dnssec) is set and O(state=present)
  type: dict
  contains:
    mode:
      description: C(unsigned), C(signed_ds_pending) until the DS is seen at the parent, then C(signed_active).
      type: str
    ds:
      description: The DS record to publish at the registrar.
      type: str
    dnskey:
      description: The zone's public key.
      type: str
    key_tag:
      description: Key tag of the signing key.
      type: int
    algorithm:
      description: Signing algorithm.
      type: str
    ds_at_parent:
      description: Whether the DS was found at the parent zone.
      type: bool
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.dns import normalize_zone_name
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
    snake,
    trim_enum,
)


def dnssec_view(info):
    info = info or {}
    return dict(
        mode=trim_enum(info.get("mode"), "DNSSEC_MODE_") or "unsigned",
        algorithm=info.get("algorithm") or "",
        key_tag=int_or_zero(info.get("keyTag")),
        digest_type=int_or_zero(info.get("digestType")),
        ds=info.get("ds") or "",
        dnskey=info.get("dnskey") or "",
        ds_at_parent=bool(info.get("dsAtParent")),
        nsec_mode=trim_enum(info.get("nsecMode"), "NSEC_MODE_"),
    )


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
        force=dict(type="bool", default=False),
        dnssec=dict(type="bool"),
        dnssec_force_disable=dict(type="bool", default=False),
        check_delegation=dict(type="bool", default=False),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    name = normalize_zone_name(p["name"])
    zones = nr.call("listing DNS zones", c.list_dns_zones)
    zone = next((z for z in zones if normalize_zone_name(z.get("name")) == name), None)
    before = snake(zone) if zone else {}
    changed = False

    if p["state"] == "absent":
        if zone:
            if not module.check_mode:
                try:
                    c.delete_dns_zone(zone["id"], p["force"])
                except Exception as e:  # pylint: disable=broad-except
                    hint = ""
                    if "dnssec" in str(e).lower() or " ds" in str(e).lower():
                        hint = " If DNSSEC is active, remove the DS record at your registrar first, or set force=true."
                    module.fail_json(msg="deleting DNS zone %s: %s.%s" % (name, e, hint))
            module.exit_json(changed=True, zone={}, diff=dict(before=before, after={}))
        module.exit_json(changed=False, zone={})

    if not zone:
        changed = True
        if module.check_mode:
            after = dict(name=name)
            module.exit_json(changed=True, zone=after, diff=dict(before={}, after=after))
        zone = nr.call("creating DNS zone %s" % name, c.create_dns_zone, name)

    result = {}
    if p["dnssec"] is not None:
        info = nr.call("reading DNSSEC for %s" % name, c.get_dnssec, zone["id"])
        signed = trim_enum(info.get("mode"), "DNSSEC_MODE_") not in ("", "unsigned")
        if p["dnssec"] and not signed:
            changed = True
            if not module.check_mode:
                info = nr.call("enabling DNSSEC for %s" % name, c.enable_dnssec, zone["id"])
        elif not p["dnssec"] and signed:
            changed = True
            if not module.check_mode:
                info = nr.call("disabling DNSSEC for %s" % name, c.disable_dnssec, zone["id"], p["dnssec_force_disable"])
        if p["dnssec"] and not module.check_mode and info.get("dsAtParent") is False:
            # Cheap re-check so the returned mode is current after the user published the DS.
            try:
                info = c.check_dnssec_ds(zone["id"]) or info
            except Exception:  # an informational refresh only
                pass
        result["dnssec"] = dnssec_view(info)

    if p["check_delegation"] and not module.check_mode:
        zone = nr.call("checking delegation of %s" % name, c.check_dns_zone_delegation, zone["id"]) or zone

    if changed and not module.check_mode:
        zone = nr.call("reading DNS zone %s" % name, c.get_dns_zone, zone["id"]) or zone
    after = snake(zone)
    module.exit_json(changed=changed, zone=after, diff=dict(before=before, after=after), **result)


if __name__ == "__main__":
    main()
