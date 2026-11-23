#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: firewall_ruleset_info
short_description: List NodeRings firewall rulesets and address groups
version_added: 0.1.0
description:
  - Lists firewall rulesets with their rules, and the organization's address groups.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: none
options:
  name:
    description:
      - Only return the ruleset with this name.
    type: str
  attachment:
    description:
      - Only return rulesets that are V(attached) to at least one VM, or V(unattached) ones.
    type: str
    choices: [all, attached, unattached]
    default: all
  include_rules:
    description:
      - Also return each ruleset's rules (one extra request per ruleset).
    type: bool
    default: true
"""

EXAMPLES = r"""
- name: Rulesets that no VM uses
  noderings.cloud.firewall_ruleset_info:
    attachment: unattached
  register: unused
"""

RETURN = r"""
rulesets:
  description: The rulesets.
  returned: always
  type: list
  elements: dict
address_groups:
  description: The organization's address groups.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.firewall import prefixes_from_api, rule_view
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    int_or_zero,
    noderings_argument_spec,
)

ATTACHMENT = {
    "all": None,
    "attached": "FIREWALL_RULESET_ATTACHMENT_FILTER_ATTACHED",
    "unattached": "FIREWALL_RULESET_ATTACHMENT_FILTER_UNATTACHED",
}


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str"),
        attachment=dict(type="str", default="all", choices=list(ATTACHMENT)),
        include_rules=dict(type="bool", default=True),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    sets = nr.call("listing rulesets", c.list_firewall_rulesets, p["name"], ATTACHMENT[p["attachment"]])
    if p["name"]:
        sets = [s for s in sets if s.get("name") == p["name"]]
    out = []
    for s in sets:
        item = dict(id=s.get("id"), name=s.get("name"), rule_count=int_or_zero(s.get("ruleCount")),
                    attached_vm_count=int_or_zero(s.get("attachedVmCount")), attached_vm_hostnames=s.get("attachedVmHostnames") or [])
        if p["include_rules"]:
            item["rules"] = [rule_view(r) for r in nr.call("listing rules of %s" % s.get("name"), c.list_firewall_rules, s["id"])]
        out.append(item)
    groups = nr.call("listing address groups", c.list_firewall_address_groups)
    groups = [dict(id=g.get("id"), name=g.get("name"), cidrs=prefixes_from_api(g.get("prefixes"))) for g in groups]
    module.exit_json(changed=False, rulesets=out, address_groups=groups)


if __name__ == "__main__":
    main()
