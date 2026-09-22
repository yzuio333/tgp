"""Регрессии маршрутизации лотов по форумным топикам."""
import unittest
from types import SimpleNamespace

from app.core import categories


def listing(**overrides):
    values = {
        "currency": "stars",
        "price": 500,
        "title": "Snoop Dogg",
        "collection": "Snoop Dogg",
        "backdrop": "",
        "model_rarity": 0,
        "value_usd_amount": 0,
        "is_rich": False,
        "owner": "",
        "owner_username": "",
        "owner_id": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class CategoryRoutingTests(unittest.TestCase):
    def test_price_route_is_available_without_owner_profile(self):
        matched = categories.classify(listing())
        route = categories.primary_category(
            matched, topics={"price_300_1000": 8}
        )
        self.assertEqual(route, "price_300_1000")

    def test_full_profile_country_routes_to_arabic_topic(self):
        owner = SimpleNamespace(known=True, country="AE", about="", lang="")
        matched = categories.classify(listing(), owner_info=owner)
        route = categories.primary_category(
            matched,
            topics={"arabic": 33, "price_300_1000": 8},
        )
        self.assertEqual(route, "arabic")

    def test_unbound_specific_topic_falls_back_to_price_topic(self):
        owner = SimpleNamespace(known=True, country="AE", about="", lang="")
        matched = categories.classify(listing(), owner_info=owner)
        route = categories.primary_category(
            matched, topics={"price_300_1000": 8}
        )
        self.assertEqual(route, "price_300_1000")


if __name__ == "__main__":
    unittest.main()
