# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.noderings.cloud.plugins.modules import marketplace_offer_info
from ansible_collections.noderings.cloud.tests.unit.plugins.modules.market_fakeapi import ACME, ACME_ID, market_routes

ARGS = dict(plan_code="SC-GC-1C-1G-20", country="United States", city="Ashburn", billing_type="usage")


@pytest.mark.parametrize("provider", [ACME_ID, "acme-hosting", "Acme Hosting", "  ACME hosting "])
def test_offers_from_the_named_provider(api, run, provider):
    market_routes(api)
    r = run(marketplace_offer_info, dict(ARGS, provider=provider))
    assert not r.get("failed"), r
    assert [o["provider_name"] for o in r["offers"]] == ["Acme Hosting"] and r["offer"]["plan_id"] == "plan-acme"


def test_without_a_provider_the_cheapest_comes_first(api, run):
    market_routes(api)
    r = run(marketplace_offer_info, ARGS)
    assert [o["provider_name"] for o in r["offers"]] == ["Cheap Hosting", "Acme Hosting"]


def test_unknown_provider_fails(api, run):
    market_routes(api)
    r = run(marketplace_offer_info, dict(ARGS, provider="Nobody Hosting"))
    assert r["failed"] and "from provider Nobody Hosting" in r["msg"]
    r = run(marketplace_offer_info, dict(ARGS, provider="Nobody Hosting", fail_if_none=False))
    assert not r.get("failed") and r["offers"] == [] and r["offer"] == {}


def test_ambiguous_provider_name_fails(api, run):
    market_routes(api, extra=[dict(ACME, organizationId="66666666-6666-6666-6666-666666666666")])
    r = run(marketplace_offer_info, dict(ARGS, provider="ACME HOSTING"))
    assert r["failed"] and "more than one provider is named ACME HOSTING; give its provider ID or storefront slug instead" in r["msg"]


def test_storefront_errors_other_than_not_found_propagate(api, run):
    market_routes(api)

    @api.route("GET", "/v1/public/storefronts/([^/]+)")
    def broken(q, b, slug):
        return 500, {"code": 13, "message": "storefront service down"}

    api.routes.insert(0, api.routes.pop())  # take precedence over the working route
    r = run(marketplace_offer_info, dict(ARGS, provider="acme-hosting"))
    assert r["failed"] and "storefront service down" in r["msg"]


def test_provider_is_mutually_exclusive(api, run):
    market_routes(api)
    r = run(marketplace_offer_info, dict(ARGS, provider="Acme Hosting", storefront_slug="acme-hosting"))
    assert r["failed"] and "mutually exclusive" in r["msg"]
