#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: organization_info
short_description: Get the NodeRings organization the token acts in
version_added: 0.1.0
description:
  - Returns the organization the API token acts in, and every organization the token can reach.
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
"""

EXAMPLES = r"""
- name: Show which organization the playbook acts in
  noderings.cloud.organization_info:
  register: org

- name: Print it
  ansible.builtin.debug:
    msg: "Acting in {{ org.organization.name }} ({{ org.organization.id }})"
"""

RETURN = r"""
organization:
  description: The organization the token acts in.
  returned: always
  type: dict
  sample:
    id: 3f1c2b9a-8e1d-4c55-9a77-1b2c3d4e5f60
    name: Example Ltd
    description: ""
    type: ORGANIZATION_TYPE_CLIENT
    is_verified: true
organizations:
  description: Every organization the token can act in.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsModule,
    noderings_argument_spec,
    pick,
)


def main():
    module = AnsibleModule(argument_spec=noderings_argument_spec(), supports_check_mode=True)
    nr = NodeRingsModule(module)
    org = nr.call("reading the organization", nr.client.get_organization)
    orgs = nr.call("listing organizations", nr.client.list_organizations)
    keys = ("id", "name", "description", "type", "isVerified")
    module.exit_json(changed=False, organization=pick(org, *keys), organizations=[pick(o, *keys) for o in orgs or []])


if __name__ == "__main__":
    main()
