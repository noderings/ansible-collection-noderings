# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Marketplace routes for the fake API: two providers sell SC-GC-1C-1G-20 in Ashburn.

Cheap Hosting is the cheaper one; Acme Hosting has the storefront acme-hosting.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


ACME_ID = "33333333-3333-3333-3333-333333333333"
CHEAP = {"organizationId": "11111111-1111-1111-1111-111111111111", "organizationName": "Cheap Hosting", "planId": "plan-cheap",
         "planRegions": [{"country": "United States", "city": "Ashburn", "regionId": "region-cheap"}], "rating": 4.0,
         "planPrices": [{"unitAmount": "0.007", "unitName": "per compute-hour"}]}
ACME = {"organizationId": ACME_ID, "organizationName": "Acme Hosting", "planId": "plan-acme",
        "planRegions": [{"country": "United States", "city": "Ashburn", "regionId": "region-acme"}], "rating": 4.8,
        "planPrices": [{"unitAmount": "0.012", "unitName": "per compute-hour"}]}


def market_routes(api, extra=(), asset_type="ASSET_TYPE_VM"):
    """Add the provider list, provider and storefront routes; ``extra`` adds more providers to the list."""

    @api.route("GET", "/v1/marketplace/providers")
    def providers(q, b):
        return 200, {"providers": [CHEAP, ACME] + list(extra)}

    @api.route("GET", "/v1/marketplace/providers/([^/]+)")
    def provider(q, b, provider_id):
        if provider_id != ACME_ID:
            return 404, {"code": 5, "message": "provider not found"}
        return 200, {"provider": {
            "provider": {"organizationId": ACME_ID, "organizationName": "Acme Hosting", "rating": 4.8},
            "availablePlans": [{"planId": "plan-acme", "planCode": "SC-GC-1C-1G-20", "billingType": "BILLING_TYPE_USAGE",
                                "assetType": asset_type, "regions": ACME["planRegions"], "planPrices": ACME["planPrices"]}],
        }}

    @api.route("GET", "/v1/public/storefronts/([^/]+)")
    def storefront(q, b, slug):
        if slug != "acme-hosting":
            return 404, {"code": 5, "message": "storefront not found"}
        return 200, {"storefront": {"slug": slug, "providerId": ACME_ID}}
