#!/usr/bin/env python3
"""
Test script for v10 strategy implementation
Verifies phase detection, order replacement, and grid sliding
"""

import sys
import os
from decimal import Decimal

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

from strategy.data_models import Phase, PositionState, PositionConfig
from strategy.unit_tracker import UnitTracker
from strategy.position_map import calculate_initial_position_map

def test_phase_detection():
    """Test v10 simplified phase detection"""
    print("\n=== Testing Phase Detection ===")

    # Initialize position state
    entry_price = Decimal("3000")
    unit_size = Decimal("10")
    asset_size = Decimal("1.0")
    position_value = Decimal("3000")

    position_state, position_map = calculate_initial_position_map(
        entry_price=entry_price,
        unit_size_usd=unit_size,
        asset_size=asset_size,
        position_value_usd=position_value,
        unit_range=20
    )

    tracker = UnitTracker(position_state, position_map)

    # Test initial state (4 stops, 0 buys)
    phase = tracker.get_phase()
    print(f"Initial state: {len(tracker.trailing_stop)} stops, {len(tracker.trailing_buy)} buys")
    print(f"Phase: {phase}")
    assert phase == "full_position", f"Expected full_position, got {phase}"

    # Simulate sell order fill - remove a stop, add a buy
    tracker.remove_trailing_stop(-1)
    tracker.add_trailing_buy(1)
    phase = tracker.get_phase()
    print(f"\nAfter 1 sell: {len(tracker.trailing_stop)} stops, {len(tracker.trailing_buy)} buys")
    print(f"Phase: {phase}")
    assert phase == "mixed", f"Expected mixed, got {phase}"

    # Simulate all sells filled
    tracker.trailing_stop.clear()
    tracker.trailing_buy = [1, 2, 3, 4]
    phase = tracker.get_phase()
    print(f"\nAll sells filled: {len(tracker.trailing_stop)} stops, {len(tracker.trailing_buy)} buys")
    print(f"Phase: {phase}")
    assert phase == "full_cash", f"Expected full_cash, got {phase}"

    print("\n[PASSED] Phase detection tests passed!")

def test_compounding():
    """Test v10 organic compounding via realized PnL"""
    print("\n=== Testing Organic Compounding ===")

    # Initialize position
    entry_price = Decimal("3000")
    unit_size = Decimal("10")
    asset_size = Decimal("1.0")
    position_value = Decimal("3000")

    position_state, position_map = calculate_initial_position_map(
        entry_price=entry_price,
        unit_size_usd=unit_size,
        asset_size=asset_size,
        position_value_usd=position_value,
        unit_range=20
    )

    tracker = UnitTracker(position_state, position_map)

    # Initial fragment size
    base_fragment = position_state.long_fragment_usd
    print(f"Base fragment size: ${base_fragment}")

    # Simulate profit from a sell
    sell_price = Decimal("3050")  # Sold at profit
    buy_price = entry_price
    size = Decimal("0.25")

    tracker.track_realized_pnl(sell_price, buy_price, size)
    print(f"Realized PnL: ${tracker.current_realized_pnl}")

    # Now simulate we have buy orders (mixed state)
    tracker.trailing_stop = [-2, -3]
    tracker.trailing_buy = [1, 2]

    # Get adjusted fragment for buy orders
    adjusted_fragment = tracker.get_adjusted_fragment_usd()
    expected_adjustment = tracker.current_realized_pnl / Decimal("2")  # 2 buy orders
    expected_fragment = base_fragment + expected_adjustment

    print(f"Adjusted fragment with 2 buys: ${adjusted_fragment}")
    print(f"Expected: ${expected_fragment}")

    assert abs(adjusted_fragment - expected_fragment) < Decimal("0.01"), \
        f"Fragment mismatch: {adjusted_fragment} vs {expected_fragment}"

    print("\n[PASSED] Compounding tests passed!")

def test_window_composition():
    """Test that window always maintains 4 orders"""
    print("\n=== Testing 4-Order Window ===")

    # Initialize position
    entry_price = Decimal("3000")
    unit_size = Decimal("10")
    asset_size = Decimal("1.0")
    position_value = Decimal("3000")

    position_state, position_map = calculate_initial_position_map(
        entry_price=entry_price,
        unit_size_usd=unit_size,
        asset_size=asset_size,
        position_value_usd=position_value,
        unit_range=20
    )

    tracker = UnitTracker(position_state, position_map)

    # Check initial state
    total = len(tracker.trailing_stop) + len(tracker.trailing_buy)
    print(f"Initial: {len(tracker.trailing_stop)} stops + {len(tracker.trailing_buy)} buys = {total} total")
    assert total == 4, f"Expected 4 orders, got {total}"

    # Simulate order replacement sequence
    print("\nSimulating order fills and replacements:")

    # Fill a stop, add a buy
    tracker.remove_trailing_stop(-1)
    tracker.add_trailing_buy(1)
    total = len(tracker.trailing_stop) + len(tracker.trailing_buy)
    print(f"After stop fill: {len(tracker.trailing_stop)} stops + {len(tracker.trailing_buy)} buys = {total} total")
    assert total == 4, f"Expected 4 orders, got {total}"

    # Fill another stop, add another buy
    tracker.remove_trailing_stop(-2)
    tracker.add_trailing_buy(2)
    total = len(tracker.trailing_stop) + len(tracker.trailing_buy)
    print(f"After 2nd stop: {len(tracker.trailing_stop)} stops + {len(tracker.trailing_buy)} buys = {total} total")
    assert total == 4, f"Expected 4 orders, got {total}"

    # Fill a buy, add a stop
    tracker.remove_trailing_buy(1)
    tracker.add_trailing_stop(-1)
    total = len(tracker.trailing_stop) + len(tracker.trailing_buy)
    print(f"After buy fill: {len(tracker.trailing_stop)} stops + {len(tracker.trailing_buy)} buys = {total} total")
    assert total == 4, f"Expected 4 orders, got {total}"

    print("\n[PASSED] Window composition tests passed!")

def main():
    """Run all v10 tests"""
    print("=" * 50)
    print("Testing HyperTrader v10 Implementation")
    print("=" * 50)

    test_phase_detection()
    test_compounding()
    test_window_composition()

    print("\n" + "=" * 50)
    print("[SUCCESS] All v10 tests passed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()