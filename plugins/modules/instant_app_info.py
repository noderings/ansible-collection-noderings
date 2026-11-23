#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: instant_app_info
short_description: List NodeRings instant apps (one-click applications)
version_added: 0.1.0
description:
  - Lists the applications that can be installed on a new VM with O(noderings.cloud.virtual_machine#module:instant_app).
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
  slug:
    description:
      - Return only this app, with its full details.
    type: str
  query:
    description:
      - Search text.
    type: str
  categories:
    description:
      - Only apps in these categories.
    type: list
    elements: str
    default: []
  distro:
    description:
      - Only apps that run on this distro.
    type: str
"""

EXAMPLES = r"""
- name: Find WordPress
  noderings.cloud.instant_app_info:
    query: wordpress
  register: apps
"""

RETURN = r"""
instant_apps:
  description: The apps. C(slug) is the value for O(noderings.cloud.virtual_machine#module:instant_app).
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsModule, noderings_argument_spec, snake


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(slug=dict(type="str"), query=dict(type="str"), categories=dict(type="list", elements="str", default=[]),
                         distro=dict(type="str"))
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    p = module.params
    if p["slug"]:
        app = nr.call("reading instant app %s" % p["slug"], nr.client.get_instant_app_by_slug, p["slug"])
        module.exit_json(changed=False, instant_apps=[snake(app)] if app and app.get("id") else [])
    distro = ("DISTRO_" + p["distro"].upper()) if p["distro"] else None
    apps = nr.call("listing instant apps", nr.client.list_instant_apps, p["query"], p["categories"], distro)
    module.exit_json(changed=False, instant_apps=[snake(a) for a in apps])


if __name__ == "__main__":
    main()
