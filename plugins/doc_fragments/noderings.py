# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):

    DOCUMENTATION = r"""
options:
  api_token:
    description:
      - A NodeRings service-account token.
      - Create one in the NodeRings console under C(Organization > Service accounts).
      - If not set, the value of the E(NODERINGS_TOKEN), E(NODERINGS_API_TOKEN) or E(NR_API_TOKEN) environment variable is used.
    type: str
    aliases: [token]
  api_url:
    description:
      - Base URL of the NodeRings API.
      - If not set, the value of the E(NODERINGS_API_URL) environment variable is used.
    type: str
    default: https://api.noderings.com
  organization_id:
    description:
      - Organization to act in, sent as the C(X-Organization-ID) header.
      - Defaults to the organization the token belongs to.
      - If not set, the value of the E(NODERINGS_ORGANIZATION_ID) or E(NR_ORGANIZATION_ID) environment variable is used.
    type: str
  api_timeout:
    description:
      - Timeout in seconds for a single HTTP request.
    type: int
    default: 60
  api_retries:
    description:
      - How many times a request is retried after rate limiting (HTTP 429) or a gateway error (HTTP 502, 503 or 504).
      - Orders (virtual machines, game servers, snapshots) are never retried blindly.
    type: int
    default: 5
  validate_certs:
    description:
      - Whether to validate the API's TLS certificate.
    type: bool
    default: true
notes:
  - All modules in this collection belong to the C(noderings.cloud.noderings) action group,
    so connection options can be set once with C(module_defaults).
requirements:
  - python >= 3.9
"""

    WAIT = r"""
options:
  wait:
    description:
      - Wait until the operation has finished before returning.
    type: bool
    default: true
  wait_timeout:
    description:
      - How long to wait, in seconds, when O(wait=true).
    type: int
    default: 1800
"""
