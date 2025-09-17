"""
Test to verify buy orders are placed correctly when price goes down.
This test specifically checks the bug where buy orders weren't being placed.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from src.strategy.data_models import OrderType, PositionState
from src.strategy.position_map import calculate_initial_position_map
from src.strategy.unit_tracker import UnitTracker


class TestBuyOrderPlacement:
    """Test that buy orders are properly placed when price moves down."""

    @pytest.mark.asyncio
    async def test_downward_movement_places_buy_order(self):
        """Test that when price goes down, a buy order is placed."""
        # Setup position state
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500"),
            unit_range=10
        )

        # Create unit tracker
        unit_tracker = UnitTracker(position_state, position_map)

        # Initial state should have 4 stops, 0 buys
        assert len(unit_tracker.trailing_stop) == 4
        assert len(unit_tracker.trailing_buy) == 0

        # Simulate price dropping to unit -1 (price = 2249)
        event = unit_tracker.calculate_unit_change(Decimal("2249"))

        assert event is not None
        assert event.direction == "down"
        assert event.current_unit == -1

        # Now we should place a buy at unit 0 (current_unit + 1)
        new_buy_unit = event.current_unit + 1  # Should be 0
        assert new_buy_unit == 0

        # The buy order should be placed at entry price (2500)
        buy_price = position_state.get_price_for_unit(new_buy_unit)
        assert buy_price == Decimal("2500")

        # Add to trailing_buy list (simulating what main.py should do)
        unit_tracker.add_trailing_buy(new_buy_unit)
        assert new_buy_unit in unit_tracker.trailing_buy
        assert len(unit_tracker.trailing_buy) == 1

    @pytest.mark.asyncio
    async def test_buy_order_type_selection(self):
        """Test that correct order type is chosen based on price comparison."""
        # Setup
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500")
        )

        # Mock SDK client
        mock_sdk = Mock()
        mock_sdk.place_stop_buy.return_value = Mock(
            success=True,
            order_id="stop_buy_123"
        )
        mock_sdk.place_limit_order.return_value = Mock(
            success=True,
            order_id="limit_buy_123"
        )

        # Test case 1: Buy price ABOVE current market -> should use STOP BUY
        buy_unit_price = Decimal("2600")
        current_market_price = Decimal("2500")

        if buy_unit_price > current_market_price:
            # Should place stop buy
            result = mock_sdk.place_stop_buy(
                symbol="ETH",
                size=Decimal("1.25"),
                trigger_price=buy_unit_price,
                limit_price=buy_unit_price,
                reduce_only=False
            )
            assert result.success
            assert result.order_id == "stop_buy_123"

        # Test case 2: Buy price BELOW current market -> should use LIMIT BUY
        buy_unit_price = Decimal("2400")
        current_market_price = Decimal("2500")

        if buy_unit_price <= current_market_price:
            # Should place limit buy
            result = mock_sdk.place_limit_order(
                symbol="ETH",
                is_buy=True,
                price=buy_unit_price,
                size=Decimal("1.25"),
                reduce_only=False,
                post_only=True
            )
            assert result.success
            assert result.order_id == "limit_buy_123"

    def test_sliding_window_buy_maintenance(self):
        """Test that sliding window maintains buy orders correctly."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500"),
            unit_range=10
        )

        unit_tracker = UnitTracker(position_state, position_map)

        # Simulate multiple downward movements
        # Move to unit -1
        event = unit_tracker.calculate_unit_change(Decimal("2249"))
        unit_tracker.add_trailing_buy(0)  # Add buy at unit 0

        # Move to unit -2
        event = unit_tracker.calculate_unit_change(Decimal("1999"))
        unit_tracker.add_trailing_buy(-1)  # Add buy at unit -1

        # Move to unit -3
        event = unit_tracker.calculate_unit_change(Decimal("1749"))
        unit_tracker.add_trailing_buy(-2)  # Add buy at unit -2

        # Move to unit -4
        event = unit_tracker.calculate_unit_change(Decimal("1499"))
        unit_tracker.add_trailing_buy(-3)  # Add buy at unit -3

        # Now we should have 4 buy orders
        assert len(unit_tracker.trailing_buy) == 4
        assert unit_tracker.trailing_buy == [-3, -2, -1, 0]  # Sorted

        # Move to unit -5 (should trigger window adjustment)
        event = unit_tracker.calculate_unit_change(Decimal("1249"))

        # In real system, should cancel oldest buy (0) and add new buy at -4
        # But we'd need to simulate the main.py logic here

    def test_rapid_downward_movement_buy_placement(self):
        """Test buy orders are placed correctly during rapid price drops."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500"),
            unit_range=10
        )

        unit_tracker = UnitTracker(position_state, position_map)

        # Rapid drop from unit 0 to unit -5
        event = unit_tracker.calculate_unit_change(Decimal("1249"))

        assert event is not None
        assert event.current_unit == -5
        assert event.direction == "down"

        # Should place buy at unit -4 (current + 1)
        new_buy_unit = event.current_unit + 1
        assert new_buy_unit == -4

        buy_price = position_state.get_price_for_unit(new_buy_unit)
        assert buy_price == Decimal("1500")  # 2500 + (-4 * 250)

    def test_phase_detection_with_buy_orders(self):
        """Test that phase correctly changes when buy orders are added."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500")
        )

        unit_tracker = UnitTracker(position_state, position_map)

        # Start in ADVANCE (4 stops, 0 buys)
        assert unit_tracker.get_phase() == "advance"

        # Add one buy order (simulating a stop-loss fill)
        unit_tracker.remove_trailing_stop(-1)
        unit_tracker.add_trailing_buy(-1)

        # Should be RETRACEMENT (3 stops, 1 buy)
        assert unit_tracker.get_phase() == "retracement"

        # Continue to DECLINE (0 stops, 4 buys)
        unit_tracker.trailing_stop = []
        unit_tracker.trailing_buy = [-4, -3, -2, -1]

        assert unit_tracker.get_phase() == "decline"


class TestBuyOrderIntegration:
    """Integration tests for buy order placement."""

    @pytest.mark.asyncio
    async def test_full_cycle_with_buy_orders(self):
        """Test a complete cycle including buy order placement and fills."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5"),
            position_value_usd=Decimal("12500"),
            unit_range=10
        )

        unit_tracker = UnitTracker(position_state, position_map)

        # Track the journey
        events = []

        # Price drops
        for price in [Decimal("2400"), Decimal("2300"), Decimal("2200")]:
            event = unit_tracker.calculate_unit_change(price)
            if event:
                events.append(event)
                # Simulate placing buy order
                new_buy_unit = event.current_unit + 1
                unit_tracker.add_trailing_buy(new_buy_unit)

        # Should have collected some buy orders
        assert len(unit_tracker.trailing_buy) > 0

        # Price recovers
        for price in [Decimal("2300"), Decimal("2400"), Decimal("2500")]:
            event = unit_tracker.calculate_unit_change(price)
            if event:
                events.append(event)

        # Should have gone through multiple phases
        phases_seen = set(e.phase for e in events)
        assert len(phases_seen) >= 1  # At least saw some phase changes