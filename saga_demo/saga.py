from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from saga_demo.models import OrderRequest
from saga_demo.services import BillingService, DiscountsService, InventoryService
from saga_demo.store import Store


class SagaError(Exception):
    pass


class Step(ABC):
    def __init__(self, store: Store, order_id: int):
        self.store = store
        self.order_id = order_id

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def compensate(self) -> None: ...

    def run(self) -> None:
        self.store.log(f"[order={self.order_id}] STEP {self.name()}")
        self.execute()
        self.store.log(f"[order={self.order_id}] STEP {self.name()} OK")

    def run_compensation(self) -> None:
        self.store.log(f"[order={self.order_id}] COMPENSATE {self.name()}")
        self.compensate()
        self.store.log(f"[order={self.order_id}] COMPENSATE {self.name()} OK")


class ReservePromoUse(Step):
    def __init__(self, store: Store, order_id: int, promo_code: str):
        super().__init__(store, order_id)
        self.promo_code = promo_code
        self.service = DiscountsService(store)

    def name(self) -> str:
        return "ReservePromoUse"

    def execute(self) -> None:
        self.service.reserve_promo_use(self.order_id, self.promo_code)

    def compensate(self) -> None:
        self.service.release_promo_use(self.order_id, self.promo_code)


class ReserveInventory(Step):
    def __init__(self, store: Store, order_id: int, sku: str, qty: int):
        super().__init__(store, order_id)
        self.sku = sku
        self.qty = qty
        self.service = InventoryService(store)

    def name(self) -> str:
        return "ReserveInventory"

    def execute(self) -> None:
        self.service.reserve_inventory(self.order_id, self.sku, self.qty)

    def compensate(self) -> None:
        self.service.release_inventory(self.order_id, self.sku, self.qty)


class ChargeUserBalance(Step):
    def __init__(self, store: Store, order_id: int, user_id: int, amount: Decimal):
        super().__init__(store, order_id)
        self.user_id = user_id
        self.amount = amount
        self.service = BillingService(store)

    def name(self) -> str:
        return "ChargeUserBalance"

    def execute(self) -> None:
        self.service.charge_user_balance(self.order_id, self.user_id, self.amount)

    def compensate(self) -> None:
        self.service.refund_user_balance(self.order_id, self.user_id, self.amount)


class FinalizeOrder(Step):
    def name(self) -> str:
        return "FinalizeOrder"

    def execute(self) -> None:
        # В этом упрощённом демо "финализация" — просто лог.
        self.store.log(f"[order={self.order_id}] order finalized")

    def compensate(self) -> None:
        # Обычно тут либо нет компенсации, либо она зависит от бизнеса.
        self.store.log(f"[order={self.order_id}] finalize has no compensation")


@dataclass(slots=True)
class OrderAmounts:
    base_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal


class SagaOrchestrator:
    def __init__(self, store: Store):
        self.store = store

    def _calculate_amounts(self, req: OrderRequest) -> OrderAmounts:
        item = self.store.items.get(req.sku)
        if not item:
            raise ValueError(f"Item {req.sku} not found")

        base = (item.price * Decimal(req.qty)).quantize(Decimal("0.01"))
        discount = DiscountsService(self.store).calculate_discount(req.promo_code, base).quantize(Decimal("0.01"))
        final = (base - discount).quantize(Decimal("0.01"))
        return OrderAmounts(base_amount=base, discount_amount=discount, final_amount=final)

    def execute(self, req: OrderRequest, fail_at_step: Optional[str] = None) -> bool:
        self.store.log(f"[order={req.order_id}] SAGA START user={req.user_id} sku={req.sku} qty={req.qty} promo={req.promo_code}")

        if req.qty <= 0:
            raise ValueError("qty must be > 0")
        if req.user_id not in self.store.users:
            raise ValueError(f"User {req.user_id} not found")

        amounts = self._calculate_amounts(req)
        self.store.log(
            f"[order={req.order_id}] amounts: base={amounts.base_amount} discount={amounts.discount_amount} final={amounts.final_amount}"
        )

        steps: List[Step] = []
        if req.promo_code:
            steps.append(ReservePromoUse(self.store, req.order_id, req.promo_code))
        steps.append(ReserveInventory(self.store, req.order_id, req.sku, req.qty))
        steps.append(ChargeUserBalance(self.store, req.order_id, req.user_id, amounts.final_amount))
        steps.append(FinalizeOrder(self.store, req.order_id))

        completed: List[Step] = []
        try:
            for step in steps:
                if fail_at_step == step.name():
                    raise SagaError(f"Artificial failure at step {step.name()}")
                step.run()
                completed.append(step)

            self.store.log(f"[order={req.order_id}] SAGA OK")
            return True
        except Exception as e:
            self.store.log(f"[order={req.order_id}] SAGA FAILED: {e}")
            for step in reversed(completed):
                try:
                    step.run_compensation()
                except Exception as comp_exc:
                    self.store.log(f"[order={req.order_id}] COMPENSATION FAILED at {step.name()}: {comp_exc}")
            self.store.log(f"[order={req.order_id}] SAGA END (failed)")
            return False

