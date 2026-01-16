from __future__ import annotations

import argparse
import logging
from decimal import Decimal

from saga_demo.models import OrderRequest
from saga_demo.saga import SagaOrchestrator
from saga_demo.store import Store


def seed(store: Store) -> None:
    store.add_user(1, Decimal("1000.00"))
    store.add_user(2, Decimal("50.00"))

    store.add_item("ITEM001", price=Decimal("100.00"), on_hand=10)
    store.add_item("ITEM002", price=Decimal("100.00"), on_hand=5)

    store.add_promo("DISCOUNT10", remaining_uses=5, discount_amount=Decimal("10.00"))
    store.add_promo("EXPIRED", remaining_uses=0, discount_amount=Decimal("15.00"))


def main() -> None:
    # максимально простые логи без "шумных" префиксов
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    p = argparse.ArgumentParser(description="Run one order through Saga and print logs.")
    p.add_argument("--order-id", type=int, default=1)
    p.add_argument("--user-id", type=int, default=1)
    p.add_argument("--sku", type=str, default="ITEM001")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--promo", type=str, default=None)
    p.add_argument("--fail-at", type=str, default=None, help="Имя шага для искусственного падения (например FinalizeOrder)")
    args = p.parse_args()

    store = Store()
    seed(store)

    saga = SagaOrchestrator(store)
    ok = saga.execute(
        OrderRequest(
            order_id=args.order_id,
            user_id=args.user_id,
            sku=args.sku,
            qty=args.qty,
            promo_code=args.promo,
        ),
        fail_at_step=args.fail_at,
    )

    print("\n=== RESULT ===")
    print("success:", ok)
    print("users:", store.users)
    print("items:", store.items)
    print("promos:", store.promos)


if __name__ == "__main__":
    main()

