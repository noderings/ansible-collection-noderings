# -*- coding: utf-8 -*-
# Copyright (c) NodeRings contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.noderings.cloud.plugins.module_utils import marketplace
from ansible_collections.noderings.cloud.plugins.module_utils.noderings import NodeRingsError


def test_main_price_prefers_compute_meter():
    prices = [{"unitAmount": "0.000041", "unitName": "per GB-hour"}, {"unitAmount": "0.007", "unitName": "per compute-hour"},
              {"unitAmount": "3", "unitName": "per GB"}]
    assert marketplace.main_price(prices) == 0.007
    assert marketplace.main_price([{"unitAmount": "5", "pricingModel": "PRICING_MODEL_FIXED"}, {"unitAmount": "0.1", "unitName": "per GB"}]) == 5
    assert marketplace.main_price([]) == float("inf")


class FakeMarket(object):
    def __init__(self, providers):
        self.providers = providers

    def list_providers(self, code, country, city, billing, ipv6):
        return self.providers


def provider(name, price, caps, rating=0.0):
    return {"organizationId": name, "organizationName": name, "planId": "plan-" + name, "capabilities": caps, "rating": rating,
            "planRegions": [{"regionId": "region-" + name, "country": "Germany", "city": "Frankfurt"}],
            "planPrices": [{"unitAmount": price, "unitName": "per compute-hour"}, {"unitAmount": "0.00001", "unitName": "per GB-hour"}]}


def test_find_offers_filters_and_sorts():
    m = FakeMarket([provider("a", "0.02", ["guest_firewall"], 4.5), provider("b", "0.01", [], 3.0), provider("c", "0.015", ["guest_firewall"], 4.9)])
    offers, located = marketplace.find_offers(m, "X", "Germany", "frankfurt", require_capabilities=["guest_firewall"])
    assert located == 3
    assert [o["provider_name"] for o in offers] == ["c", "a"]
    offers, located = marketplace.find_offers(m, "X", "Germany", "Frankfurt", sort="rating")
    assert [o["provider_name"] for o in offers] == ["c", "a", "b"]
    assert offers[0]["region_id"] == "region-c"


class FakeStorefronts(FakeMarket):
    def __init__(self, providers, error=None):
        super(FakeStorefronts, self).__init__(providers)
        self.error = error

    def get_public_storefront(self, slug):
        if self.error:
            raise self.error
        if slug == "acme":
            return {"providerId": "acme-id"}
        raise NodeRingsError(404, 5, "storefront not found")


def test_resolve_provider():
    m = FakeStorefronts([])
    assert marketplace.resolve_provider(m, "33333333-3333-3333-3333-333333333333") == ("33333333-3333-3333-3333-333333333333", None)
    assert marketplace.resolve_provider(m, " acme ") == ("acme-id", None)
    assert marketplace.resolve_provider(m, "acme-hosting") == (None, "acme-hosting")  # no such storefront: a name
    assert marketplace.resolve_provider(m, "Acme Hosting") == (None, "Acme Hosting")
    assert marketplace.resolve_provider(m, "  ") == (None, None)


def test_resolve_provider_propagates_storefront_errors_other_than_not_found():
    m = FakeStorefronts([], error=NodeRingsError(500, 13, "boom"))
    with pytest.raises(NodeRingsError):
        marketplace.resolve_provider(m, "acme")


def test_find_offers_by_provider_name():
    m = FakeStorefronts([provider("a", "0.02", []), provider("b", "0.01", [])])
    offers, located = marketplace.find_offers(m, "X", "Germany", "Frankfurt", provider=" A ")
    assert located == 1 and [o["provider_name"] for o in offers] == ["a"]
    offers, located = marketplace.find_offers(m, "X", "Germany", "Frankfurt", provider="nobody")
    assert (offers, located) == ([], 0)
    twin = dict(provider("a", "0.03", []), organizationId="other")
    m = FakeStorefronts([provider("a", "0.02", []), twin])
    with pytest.raises(marketplace.NoOfferError, match="more than one provider is named A"):
        marketplace.find_offers(m, "X", "Germany", "Frankfurt", provider="A")


def test_no_offer_message_names_the_provider():
    msg = marketplace.no_offer_message("X", "Germany", "Frankfurt", None, 0, "Acme Hosting")
    assert msg.startswith("No offer for plan code X in Frankfurt, Germany from provider Acme Hosting.")
