"""Tests for Order Saga orchestration."""
import logging
from decimal import Decimal

import pytest

from saga_demo.models import OrderRequest
from saga_demo.saga import SagaOrchestrator

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def _order_logs(store, order_id: int) -> list[str]:
    return [line for line in store.logs if f"[order={order_id}]" in line]


def test_successful_order_without_promo(store):
    """Test successful order without promo code."""
    logging.info("\n=== TEST: Successful order without promo ===")
    
    # Execute saga
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=1, user_id=1, sku="ITEM001", qty=2, promo_code=None))
    
    # Assertions
    assert success is True
    
    # Check inventory
    item = store.items["ITEM001"]
    assert item.on_hand == 8  # 10 - 2
    
    # Check balance
    user = store.users[1]
    assert user.balance == Decimal("800.00")  # 1000 - 200
    
    logs = _order_logs(store, 1)
    assert any("STEP ReservePromoUse" in l for l in logs) is False
    assert any("STEP ReserveInventory OK" in l for l in logs)
    assert any("STEP ChargeUserBalance OK" in l for l in logs)
    assert any("STEP FinalizeOrder OK" in l for l in logs)
    assert any("SAGA OK" in l for l in logs)
    
    logging.info("✓ Order completed successfully")


def test_successful_order_with_promo(store):
    """Test successful order with promo code."""
    logging.info("\n=== TEST: Successful order with promo code ===")
    
    # Get initial promo uses
    promo = store.promos["DISCOUNT10"]
    initial_uses = promo.remaining_uses
    
    # Execute saga
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=2, user_id=1, sku="ITEM001", qty=1, promo_code="DISCOUNT10"))
    
    # Assertions
    assert success is True
    
    # Check promo code usage
    assert promo.remaining_uses == initial_uses - 1
    
    # Check inventory
    item = store.items["ITEM001"]
    assert item.on_hand == 9  # 10 - 1
    
    # Check balance (discount applied)
    user = store.users[1]
    assert user.balance == Decimal("910.00")  # 1000 - 90
    
    logs = _order_logs(store, 2)
    assert any("STEP ReservePromoUse OK" in l for l in logs)
    assert any("SAGA OK" in l for l in logs)
    logging.info("✓ Order with promo completed successfully")


def test_fail_on_insufficient_promo_uses(store):
    """Test failure when promo code has no remaining uses."""
    logging.info("\n=== TEST: Fail on insufficient promo uses ===")
    
    # Execute saga (should fail)
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=3, user_id=1, sku="ITEM001", qty=1, promo_code="EXPIRED"))
    
    # Assertions
    assert success is False
    
    # Check that inventory was NOT reserved
    item = store.items["ITEM001"]
    assert item.on_hand == 10  # Unchanged
    
    # Check that balance was NOT charged
    user = store.users[1]
    assert user.balance == Decimal("1000.00")  # Unchanged
    
    logs = _order_logs(store, 3)
    assert any("STEP ReservePromoUse OK" in l for l in logs) is False
    assert any("SAGA FAILED" in l for l in logs)
    assert any("COMPENSATE" in l for l in logs) is False
    
    logging.info("✓ Correctly failed on insufficient promo uses")


def test_fail_on_insufficient_inventory(store):
    """Test failure and compensation when inventory is insufficient."""
    logging.info("\n=== TEST: Fail on insufficient inventory ===")
    
    # Get initial promo uses
    promo = store.promos["DISCOUNT10"]
    initial_uses = promo.remaining_uses
    
    # Execute saga (should fail)
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=4, user_id=1, sku="ITEM001", qty=20, promo_code="DISCOUNT10"))
    
    # Assertions
    assert success is False
    
    # Check that promo was COMPENSATED (released)
    assert promo.remaining_uses == initial_uses  # Restored
    
    # Check inventory unchanged
    item = store.items["ITEM001"]
    assert item.on_hand == 10  # Unchanged
    
    # Check balance unchanged
    user = store.users[1]
    assert user.balance == Decimal("1000.00")  # Unchanged
    
    logs = _order_logs(store, 4)
    assert any("COMPENSATE ReservePromoUse OK" in l for l in logs)
    assert any("COMPENSATE ReserveInventory" in l for l in logs) is False  # склад не успели зарезервировать
    
    logging.info("✓ Correctly compensated promo use after inventory failure")


def test_fail_on_insufficient_balance(store):
    """Test failure and compensation when user balance is insufficient."""
    logging.info("\n=== TEST: Fail on insufficient balance ===")
    
    # Get initial states
    promo = store.promos["DISCOUNT10"]
    initial_promo_uses = promo.remaining_uses
    
    item = store.items["ITEM002"]
    initial_inventory = item.on_hand
    
    # Execute saga (should fail)
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=5, user_id=2, sku="ITEM002", qty=2, promo_code="DISCOUNT10"))
    
    # Assertions
    assert success is False
    
    # Check that promo was COMPENSATED
    assert promo.remaining_uses == initial_promo_uses  # Restored
    
    # Check that inventory was COMPENSATED
    assert item.on_hand == initial_inventory  # Restored
    
    # Check balance unchanged
    user = store.users[2]
    assert user.balance == Decimal("50.00")  # Unchanged
    
    logs = _order_logs(store, 5)
    assert any("COMPENSATE ReserveInventory OK" in l for l in logs)
    assert any("COMPENSATE ReservePromoUse OK" in l for l in logs)
    assert any("COMPENSATE ChargeUserBalance" in l for l in logs) is False  # списание не прошло
    
    logging.info("✓ Correctly compensated inventory and promo after balance failure")


def test_artificial_failure_at_finalize(store):
    """Test artificial failure at FinalizeOrder step to demonstrate full compensation."""
    logging.info("\n=== TEST: Artificial failure at FinalizeOrder ===")
    
    # Get initial states
    promo = store.promos["DISCOUNT10"]
    initial_promo_uses = promo.remaining_uses
    
    item = store.items["ITEM001"]
    initial_inventory = item.on_hand
    
    user = store.users[1]
    initial_balance = user.balance
    
    # Execute saga with artificial failure at FinalizeOrder
    saga = SagaOrchestrator(store)
    success = saga.execute(
        OrderRequest(order_id=6, user_id=1, sku="ITEM001", qty=1, promo_code="DISCOUNT10"),
        fail_at_step="FinalizeOrder",
    )
    
    # Assertions
    assert success is False
    
    # Check that ALL resources were COMPENSATED
    assert promo.remaining_uses == initial_promo_uses  # Restored
    
    assert item.on_hand == initial_inventory  # Restored
    
    assert user.balance == initial_balance  # Restored
    
    logs = _order_logs(store, 6)
    assert any("COMPENSATE ChargeUserBalance OK" in l for l in logs)
    assert any("COMPENSATE ReserveInventory OK" in l for l in logs)
    assert any("COMPENSATE ReservePromoUse OK" in l for l in logs)
    
    logging.info("✓ All compensations executed successfully after late-stage failure")


def test_order_without_promo_succeeds(store):
    """Test that order without promo code skips promo step."""
    logging.info("\n=== TEST: Order without promo skips promo step ===")
    
    # Execute saga
    saga = SagaOrchestrator(store)
    success = saga.execute(OrderRequest(order_id=7, user_id=1, sku="ITEM002", qty=1, promo_code=None))
    
    # Assertions
    assert success is True
    
    logs = _order_logs(store, 7)
    assert any("STEP ReservePromoUse" in l for l in logs) is False
    assert any("STEP ReserveInventory OK" in l for l in logs)
    assert any("STEP ChargeUserBalance OK" in l for l in logs)
    assert any("STEP FinalizeOrder OK" in l for l in logs)
    
    logging.info("✓ Order without promo correctly skipped promo step")
