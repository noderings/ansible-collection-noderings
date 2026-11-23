#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: distro_info
short_description: List the operating systems NodeRings virtual machines can run
version_added: 0.1.0
description:
  - Lists the distros you can pass as O(noderings.cloud.virtual_machine#module:distro).
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
  family:
    description:
      - Only distros of this family, for example C(ubuntu) or C(debian).
    type: str
"""

EXAMPLES = r"""
- name: Supported Ubuntu releases
  noderings.cloud.distro_info:
    family: ubuntu
  register: distros
"""

RETURN = r"""
distros:
  description: The distros. C(distro) is the value for O(noderings.cloud.virtual_machine#module:distro).
  returned: always
  type: list
  elements: dict
  sample:
    - distro: ubuntu_24_04
      family: ubuntu
      name: Ubuntu
      version: "24.04"
      label: Ubuntu 24.04 LTS
      is_default: true
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, trim_enum


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(family=dict(type="str"))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    out = []
    for d in nr.call("listing distros", nr.client.list_distros):
        fam = trim_enum(d.get("family"), "DISTRO_FAMILY_") or (d.get("family") or "").lower()
        if module.params["family"] and fam != module.params["family"].lower():
            continue
        out.append(dict(distro=trim_enum(d.get("distro"), "DISTRO_"), family=fam, name=d.get("name"), version=d.get("version"),
                        label=d.get("label"), is_default=bool(d.get("isDefault"))))
    module.exit_json(changed=False, distros=out)


if __name__ == "__main__":
    main()
