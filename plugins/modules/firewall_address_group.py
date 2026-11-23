#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: firewall_address_group
short_description: Manage NodeRings firewall address groups
version_added: 0.1.0
description:
  - An address group is a named list of IP prefixes that firewall rules can refer to,
    for example your office networks. Changing the group updates every rule that uses it.
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
      - Name of the group. Unique within the organization.
    type: str
    required: true
  cidrs:
    description:
      - IPv4 and IPv6 addresses or prefixes, for example C(203.0.113.0/24) or C(2001:db8::/32).
      - Required when O(state=present). A plain address means a single host.
    type: list
    elements: str
    aliases: [prefixes]
  state:
    description:
      - Whether the group should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Office networks
  noderings.cloud.firewall_address_group:
    name: office
    cidrs:
      - 203.0.113.0/24
      - 2001:db8:10::/48
"""

RETURN = r"""
address_group:
  description: The group. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 5b6c7d8e-0000-4a4a-9b9b-abcdefabcdef
    name: office
    cidrs: [203.0.113.0/24, 2001:db8:10::/48]
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.firewall import (
    canonical_cidr,
    prefixes_from_api,
    prefixes_to_api,
)
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec


def view(g):
    if not g:
        return {}
    return dict(id=g.get("id"), name=g.get("name"), cidrs=prefixes_from_api(g.get("prefixes")))


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        cidrs=dict(type="list", elements="str", aliases=["prefixes"]),
        state=dict(type="str", default="present", choices=["present", "absent"]),
    )
    module = AnsibleModule(argument_spec=argument_spec, required_if=[("state", "present", ["cidrs"])], supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    name = module.params["name"]
    groups = nr.call("listing address groups", c.list_firewall_address_groups, name)
    current = c.find_by_name(groups, name)
    before = view(current)

    if module.params["state"] == "absent":
        if not current:
            module.exit_json(changed=False, address_group={})
        if not module.check_mode:
            nr.call("deleting address group %s" % name, c.delete_firewall_address_group, current["id"])
        module.exit_json(changed=True, address_group={}, diff=dict(before=before, after={}))

    try:
        prefixes = prefixes_to_api(module.params["cidrs"])
    except ValueError as e:
        module.fail_json(msg="cidrs: %s" % e)
    wanted = sorted(set(canonical_cidr(cidr) for cidr in module.params["cidrs"]))
    if current and sorted(canonical_cidr(x) for x in before["cidrs"]) == wanted:
        module.exit_json(changed=False, address_group=before)
    after = dict(before, name=name, cidrs=wanted)
    if not module.check_mode:
        if current:
            g = nr.call("updating address group %s" % name, c.update_firewall_address_group, current["id"], name, prefixes)
        else:
            g = nr.call("creating address group %s" % name, c.create_firewall_address_group, name, prefixes)
        after = view(g)
    module.exit_json(changed=True, address_group=after, diff=dict(before=before, after=after))


if __name__ == "__main__":
    main()
