from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(slots=True)
class User:
    id: int
    balance: Decimal


@dataclass(slots=True)
class InventoryItem:
    sku: str
    price: Decimal
    on_hand: int


@dataclass(slots=True)
class PromoCode:
    code: str
    remaining_uses: int
    discount_amount: Decimal


@dataclass(slots=True)
class OrderRequest:
    """
    "Запрос на заказ" — просто данные для запуска Saga.
    Мы не храним заказ как сущность в памяти: только выполняем шаги и пишем логи.
    """

    order_id: int
    user_id: int
    sku: str
    qty: int
    promo_code: Optional[str] = None

