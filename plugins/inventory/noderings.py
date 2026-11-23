# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
name: noderings
short_description: NodeRings virtual machines as an Ansible inventory
version_added: 0.1.0
description:
  - Reads the organization's virtual machines from the NodeRings API and adds them as hosts.
  - Hosts are grouped by tag (C(noderings_tag_<tag>)), city, country, hosting provider, plan code,
    billing type and power state. More groups and variables can be built with O(keyed_groups), O(groups) and O(compose).
  - The inventory file name must end with C(noderings.yml) or C(noderings.yaml).
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - constructed
  - inventory_cache
options:
  plugin:
    description:
      - Must be C(noderings.cloud.noderings).
    required: true
    choices: [noderings.cloud.noderings]
    type: str
  api_token:
    description:
      - A NodeRings service-account token.
      - Can be a Jinja template, for example C({{ lookup('ansible.builtin.env', 'MY_TOKEN') }}).
    type: str
    aliases: [token]
    env:
      - name: NODERINGS_TOKEN
      - name: NODERINGS_API_TOKEN
      - name: NR_API_TOKEN
  api_url:
    description:
      - Base URL of the NodeRings API.
    type: str
    default: https://api.noderings.com
    env:
      - name: NODERINGS_API_URL
  organization_id:
    description:
      - Organization to read, sent as C(X-Organization-ID). Defaults to the token's organization.
    type: str
    env:
      - name: NODERINGS_ORGANIZATION_ID
      - name: NR_ORGANIZATION_ID
  api_timeout:
    description:
      - Timeout in seconds for a single HTTP request.
    type: int
    default: 60
  validate_certs:
    description:
      - Whether to validate the API's TLS certificate.
    type: bool
    default: true
  hostname:
    description:
      - What to name each host.
      - V(hostname) uses the VM's hostname, V(id) its ID, V(ipv4) and V(ipv6) its address.
    type: str
    choices: [hostname, id, ipv4, ipv6]
    default: hostname
  connect_via:
    description:
      - Which address to set as C(ansible_host).
    type: str
    choices: [ipv4, ipv6]
    default: ipv4
  tags:
    description:
      - Only include VMs that have all of these tags.
    type: list
    elements: str
    default: []
  states:
    description:
      - Only include VMs in these power states. Leave empty for all.
    type: list
    elements: str
    choices: [running, stopped, created, reinstalling, unknown]
    default: []
  default_groups:
    description:
      - Add the built-in groups (tag, city, country, provider, plan code, billing type, power state).
    type: bool
    default: true
  variable_prefix:
    description:
      - Prefix of the host variables holding the VM's fields, for example C(noderings_ipv4).
    type: str
    default: noderings_
"""

EXAMPLES = r"""
# noderings.yml: every VM, grouped automatically
plugin: noderings.cloud.noderings

# noderings.yml: only running production servers, plus a group per distro
plugin: noderings.cloud.noderings
tags: [prod]
states: [running]
keyed_groups:
  - key: noderings_distro
    prefix: distro
compose:
  ansible_user: "'root'"

# noderings.yml: cache the API answer for five minutes
plugin: noderings.cloud.noderings
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_connection: /tmp/noderings-inventory
cache_timeout: 300
"""

import re

from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_native
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.noderings.cloud.plugins.module_utils.compute import vm_view
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsClient, NodeRingsError

try:
    from ansible.template import trust_as_template  # ansible-core >= 2.19
except ImportError:  # pragma: no cover
    trust_as_template = None


def _group_name(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(value or "").strip().lower()).strip("_")


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):

    NAME = "noderings.cloud.noderings"

    def verify_file(self, path):
        if super(InventoryModule, self).verify_file(path):
            return path.endswith(("noderings.yml", "noderings.yaml"))
        return False

    def _templated(self, name):
        value = self.get_option(name)
        if value and isinstance(value, str) and "{{" in value:
            if trust_as_template is not None:
                value = trust_as_template(value)
            value = self.templar.template(value)
        return value

    def _fetch(self):
        try:
            client = NodeRingsClient(
                api_url=self._templated("api_url"),
                token=self._templated("api_token"),
                organization_id=self._templated("organization_id"),
                timeout=self.get_option("api_timeout"),
                validate_certs=self.get_option("validate_certs"),
            )
            return client.list_virtual_machines()
        except (ValueError, NodeRingsError, IOError, OSError) as e:
            raise AnsibleError("NodeRings inventory: %s" % to_native(e))

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path)
        self._read_config_data(path)
        cache_key = self.get_cache_key(path)
        use_cache = self.get_option("cache") and cache
        update_cache = self.get_option("cache") and not cache
        vms = None
        if use_cache:
            try:
                vms = self._cache[cache_key]
            except KeyError:
                update_cache = True
        if vms is None:
            vms = self._fetch()
        if update_cache:
            self._cache[cache_key] = vms
        self._populate(vms)

    def _populate(self, vms):
        prefix = self.get_option("variable_prefix")
        want_tags = set(self.get_option("tags") or [])
        states = set(self.get_option("states") or [])
        strict = self.get_option("strict")
        naming = self.get_option("hostname")
        via = self.get_option("connect_via")
        self.inventory.add_group("noderings")
        for raw in vms:
            vm = vm_view(raw)
            if want_tags and not want_tags.issubset(set(vm.get("tags") or [])):
                continue
            if states and vm.get("power_state") not in states:
                continue
            name = vm.get(naming) or vm.get("hostname") or vm.get("id")
            if not name:
                continue
            host = self.inventory.add_host(name, group="noderings")
            hostvars = dict((prefix + k, v) for k, v in vm.items())
            for k, v in hostvars.items():
                self.inventory.set_variable(host, k, v)
            address = vm.get(via) or vm.get("ipv4") or vm.get("ipv6")
            if address:
                self.inventory.set_variable(host, "ansible_host", address)
            if self.get_option("default_groups"):
                groups = ["noderings_tag_" + _group_name(t) for t in vm.get("tags") or []]
                for key, value in (("city", vm.get("region_city")), ("country", vm.get("region_country")),
                                   ("provider", vm.get("provider_name")), ("plan", vm.get("plan_code")),
                                   ("billing", vm.get("billing_type")), ("state", vm.get("power_state"))):
                    if value:
                        groups.append("noderings_%s_%s" % (key, _group_name(value)))
                for g in groups:
                    self.inventory.add_group(g)
                    self.inventory.add_child(g, host)
            self._set_composite_vars(self.get_option("compose"), hostvars, host, strict=strict)
            self._add_host_to_composed_groups(self.get_option("groups"), hostvars, host, strict=strict)
            self._add_host_to_keyed_groups(self.get_option("keyed_groups"), hostvars, host, strict=strict)
