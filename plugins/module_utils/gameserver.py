# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Game server helpers shared by the game server modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsError, is_not_found, snake, trim_enum

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def gs_view(gs):
    if not gs:
        return {}
    out = snake(gs)
    out["phase"] = trim_enum(gs.get("phase"), "GAME_SERVER_PHASE_")
    out["plan_billing_type"] = trim_enum(gs.get("planBillingType"), "BILLING_TYPE_")
    out["primary_ip"] = gs.get("allocationIp") or ""
    out["primary_port"] = gs.get("allocationPort") or 0
    return out


def resolve_game_server(nr, ref, required=True):
    """Find a game server by ID or by unique name."""
    c = nr.client
    if ref and UUID_RE.match(ref):
        try:
            return c.get_game_server(ref)
        except NodeRingsError as e:
            if is_not_found(e) and not required:
                return None
            nr.fail("reading game server %s" % ref, e)
    servers = nr.call("listing game servers", c.list_game_servers)
    matches = [g for g in servers if g.get("name") == ref]
    if len(matches) > 1:
        nr.module.fail_json(msg="%d game servers are named %s; pass the ID of the one you mean" % (len(matches), ref),
                            ids=[g.get("id") for g in matches])
    if not matches:
        if required:
            nr.module.fail_json(msg="no game server is named %s" % ref)
        return None
    return nr.call("reading game server %s" % ref, c.get_game_server, matches[0]["id"])


def live_power(state):
    """Map the live state to running/offline; transitions count as where they are heading."""
    if state in ("running", "starting"):
        return "running"
    if state in ("offline", "stopping"):
        return "offline"
    return state or ""
