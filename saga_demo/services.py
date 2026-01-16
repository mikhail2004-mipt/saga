from __future__ import annotations

from decimal import Decimal

from saga_demo.store import Store


class DiscountsService:
    def __init__(self, store: Store):
        self.store = store

    def calculate_discount(self, promo_code: str | None, base_amount: Decimal) -> Decimal:
        if not promo_code:
            return Decimal("0.00")
        promo = self.store.promos.get(promo_code)
        if not promo or promo.remaining_uses <= 0:
            return Decimal("0.00")
        return min(promo.discount_amount, base_amount)

    def reserve_promo_use(self, order_id: int, promo_code: str) -> None:
        promo = self.store.promos.get(promo_code)
        if not promo:
            raise ValueError(f"Promo {promo_code} not found")
        if promo.remaining_uses <= 0:
            raise ValueError(f"Promo {promo_code} has no remaining uses")
        promo.remaining_uses -= 1
        self.store.log(f"[order={order_id}] promo reserved: {promo_code} (remaining={promo.remaining_uses})")

    def release_promo_use(self, order_id: int, promo_code: str) -> None:
        promo = self.store.promos.get(promo_code)
        if not promo:
            return
        promo.remaining_uses += 1
        self.store.log(f"[order={order_id}] promo released: {promo_code} (remaining={promo.remaining_uses})")


class InventoryService:
    def __init__(self, store: Store):
        self.store = store

    def reserve_inventory(self, order_id: int, sku: str, qty: int) -> None:
        item = self.store.items.get(sku)
        if not item:
            raise ValueError(f"Item {sku} not found")
        if item.on_hand < qty:
            raise ValueError(f"Insufficient inventory for {sku}: have={item.on_hand}, need={qty}")
        item.on_hand -= qty
        self.store.log(f"[order={order_id}] inventory reserved: {sku} qty={qty} (on_hand={item.on_hand})")

    def release_inventory(self, order_id: int, sku: str, qty: int) -> None:
        item = self.store.items.get(sku)
        if not item:
            return
        item.on_hand += qty
        self.store.log(f"[order={order_id}] inventory released: {sku} qty={qty} (on_hand={item.on_hand})")


class BillingService:
    def __init__(self, store: Store):
        self.store = store

    def charge_user_balance(self, order_id: int, user_id: int, amount: Decimal) -> None:
        user = self.store.users.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        if user.balance < amount:
            raise ValueError(f"Insufficient balance for user {user_id}: have={user.balance}, need={amount}")
        user.balance -= amount
        self.store.log(f"[order={order_id}] charged user={user_id} amount={amount} (balance={user.balance})")

    def refund_user_balance(self, order_id: int, user_id: int, amount: Decimal) -> None:
        user = self.store.users.get(user_id)
        if not user:
            return
        user.balance += amount
        self.store.log(f"[order={order_id}] refunded user={user_id} amount={amount} (balance={user.balance})")

