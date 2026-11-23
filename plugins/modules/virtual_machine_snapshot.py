#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: virtual_machine_snapshot
short_description: Take and delete snapshots of NodeRings virtual machines
version_added: 0.1.0
description:
  - Takes a snapshot of a virtual machine's disk, or deletes one.
  - Snapshots are matched by O(description), so use a unique description per snapshot, for example
    C(before-upgrade-2026-11-23).
  - The VM's hosting provider must support snapshots.
author:
  - Shaygun (@shaygun)
extends_documentation_fragment:
  - noderings.cloud.noderings
  - noderings.cloud.attributes
  - noderings.cloud.noderings.WAIT
attributes:
  check_mode:
    support: full
  diff_mode:
    support: none
options:
  virtual_machine:
    description:
      - Hostname or ID of the VM.
    type: str
    required: true
    aliases: [vm]
  description:
    description:
      - Description of the snapshot. Identifies it.
    type: str
    required: true
  state:
    description:
      - Whether the snapshot should exist.
    type: str
    choices: [present, absent]
    default: present
"""

EXAMPLES = r"""
- name: Snapshot before upgrading
  noderings.cloud.virtual_machine_snapshot:
    vm: web-1
    description: before-upgrade-{{ ansible_date_time.date }}

- name: Delete it again
  noderings.cloud.virtual_machine_snapshot:
    vm: web-1
    description: before-upgrade-2026-11-23
    state: absent
"""

RETURN = r"""
snapshot:
  description: The snapshot. Empty after O(state=absent).
  returned: always
  type: dict
  sample:
    id: 9c8b7a6d-0000-1111-2222-333344445555
    description: before-upgrade-2026-11-23
    operation_status: SNAPSHOT_OPERATION_STATUS_COMPLETED
    created_at: "2026-11-23T20:00:00Z"
"""

import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.noderings.cloud.plugins.module_utils.compute import resolve_vm
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import (
    NodeRingsError,
    NodeRingsModule,
    TimeoutError_,
    Waiter,
    is_ambiguous,
    is_not_found,
    noderings_argument_spec,
    snake,
)

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
DONE = "SNAPSHOT_OPERATION_STATUS_COMPLETED"
FAILED = "SNAPSHOT_OPERATION_STATUS_FAILED"


def main():
    argument_spec = noderings_argument_spec()
    argument_spec.update(
        virtual_machine=dict(type="str", required=True, aliases=["vm"]),
        description=dict(type="str", required=True),
        state=dict(type="str", default="present", choices=["present", "absent"]),
        wait=dict(type="bool", default=True),
        wait_timeout=dict(type="int", default=1800),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    nr = NodeRingsModule(module)
    c = nr.client
    p = module.params
    ref = p["virtual_machine"]
    vm = resolve_vm(nr, ref if UUID_RE.match(ref) else None, None if UUID_RE.match(ref) else ref)
    vm_id = vm["id"]
    waiter = Waiter(p["wait_timeout"])

    def find():
        snaps = nr.call("listing snapshots", c.list_snapshots, vm_id)
        return next((s for s in snaps if s.get("description") == p["description"]), None)

    current = find()
    if p["state"] == "absent":
        if not current:
            module.exit_json(changed=False, snapshot={})
        if not module.check_mode:
            try:
                waiter.retry_busy(lambda: c.delete_snapshot(vm_id, current["id"]))
            except NodeRingsError as e:
                if not is_not_found(e):
                    nr.fail("deleting snapshot %s" % p["description"], e)
            except TimeoutError_ as e:
                nr.fail("deleting snapshot %s" % p["description"], e)
            if p["wait"]:
                nr.call("waiting for the snapshot to be deleted", waiter.wait, "the snapshot to be deleted", lambda: (find() is None, None))
        module.exit_json(changed=True, snapshot={})

    if current and current.get("operationStatus") != FAILED:
        module.exit_json(changed=False, snapshot=snake(current))
    if module.check_mode:
        module.exit_json(changed=True, snapshot=dict(description=p["description"]))
    before_ids = set(s.get("id") for s in nr.call("listing snapshots", c.list_snapshots, vm_id))
    try:
        snap = waiter.retry_busy(lambda: c.create_snapshot(vm_id, p["description"]))
    except Exception as e:  # pylint: disable=broad-except
        if not is_ambiguous(e):
            nr.fail("taking a snapshot of %s" % vm.get("hostname"), e)
        snap = None
    if not snap or not snap.get("id"):
        # There is no idempotency key, so never retry; adopt the snapshot that appeared.
        new = [s for s in nr.call("listing snapshots", c.list_snapshots, vm_id)
               if s.get("id") not in before_ids and s.get("description") == p["description"]]
        if len(new) != 1:
            module.fail_json(msg="the snapshot request for %s failed and %d matching new snapshots appeared; check the VM's "
                                 "snapshots before running again" % (vm.get("hostname"), len(new)))
        snap = new[0]
    snap_id = snap["id"]
    if p["wait"]:
        def check():
            s = c.get_snapshot(vm_id, snap_id)
            if not s:
                return False, None
            if s.get("operationStatus") == FAILED:
                raise RuntimeError("the snapshot failed; the API does not report why")
            return s.get("operationStatus") == DONE, s

        try:
            snap = waiter.wait("the snapshot to finish", check)
        except (RuntimeError, TimeoutError_, NodeRingsError) as e:
            module.fail_json(msg="taking a snapshot of %s: %s" % (vm.get("hostname"), e), changed=True, snapshot=snake(find() or {}))
    module.exit_json(changed=True, snapshot=snake(snap or {}))


if __name__ == "__main__":
    main()
