"""Pytest fixtures for minimal saga demo (logs-only)."""

from decimal import Decimal

import pytest

from saga_demo.store import Store


@pytest.fixture
def store() -> Store:
    store = Store()

    store.add_user(1, Decimal("1000.00"))
    store.add_user(2, Decimal("50.00"))

    store.add_item("ITEM001", price=Decimal("100.00"), on_hand=10)
    store.add_item("ITEM002", price=Decimal("100.00"), on_hand=5)
    store.add_item("ITEM003", price=Decimal("50.00"), on_hand=0)  # Out of stock

    store.add_promo("DISCOUNT10", remaining_uses=5, discount_amount=Decimal("10.00"))
    store.add_promo("ONETIME", remaining_uses=1, discount_amount=Decimal("20.00"))
    store.add_promo("EXPIRED", remaining_uses=0, discount_amount=Decimal("15.00"))

    return store
