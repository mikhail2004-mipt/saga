from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List

from saga_demo.models import InventoryItem, PromoCode, User

logger = logging.getLogger(__name__)


class Store:
    """
    Минимальное хранилище в памяти.

    Мы специально НЕ храним:
    - "заказы"
    - "статусы"
    - "платежи/резервации" как отдельные сущности

    Только:
    - текущее состояние ресурсов (баланс/склад/промокоды)
    - список логов (для демонстрации и тестов)
    """

    def __init__(self) -> None:
        self.users: Dict[int, User] = {}
        self.items: Dict[str, InventoryItem] = {}
        self.promos: Dict[str, PromoCode] = {}

        self.logs: List[str] = []

    def log(self, message: str) -> None:
        self.logs.append(message)
        logger.info(message)

    # Seed helpers (удобно для тестов/демо)
    def add_user(self, user_id: int, balance: Decimal) -> None:
        self.users[user_id] = User(id=user_id, balance=balance)

    def add_item(self, sku: str, price: Decimal, on_hand: int) -> None:
        self.items[sku] = InventoryItem(sku=sku, price=price, on_hand=on_hand)

    def add_promo(self, code: str, remaining_uses: int, discount_amount: Decimal) -> None:
        self.promos[code] = PromoCode(code=code, remaining_uses=remaining_uses, discount_amount=discount_amount)

