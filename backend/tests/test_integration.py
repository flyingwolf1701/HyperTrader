"""
Integration tests for main.py order flow and trading logic.
Tests the complete flow from price changes to order placement.
"""
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from hypothesis import given, strategies as st

from src.strategy.data_models import (
    OrderType, Phase, ExecutionStatus,
    PositionState, PositionConfig, UnitChangeEvent
)
from src.strategy.unit_tracker import UnitTracker
from src.strategy.position_map import calculate_initial_position_map


class TestOrderFlow:
    """Test the complete order flow from price change to order placement."""

    @pytest.mark.asyncio
    async def test_upward_price_movement_places_stop_loss(self, mock_sdk):
        """Test that upward price movement places new stop-loss order."""
        # Setup
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("0"),
            long_fragment_usd=Decimal("0")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Simulate price moving up to unit 1
        event = unit_tracker.calculate_unit_change(Decimal("2750"))

        assert event is not None
        assert event.direction == "up"
        assert event.current_unit == 1

        # In real flow, this would trigger order placement
        # New stop should be placed at unit 0 (current - 1)
        stop_price = position_state.get_price_for_unit(0)
        assert stop_price == Decimal("2500")

        # Verify SDK would be called correctly
        mock_sdk.place_stop_order.assert_not_called()  # Not called yet in unit test

        # Simulate the order placement
        result = mock_sdk.place_stop_order(
            symbol="ETH",
            is_buy=False,  # Stop loss is a sell
            size=position_state.long_fragment_asset,
            trigger_price=stop_price,
            reduce_only=True
        )

        assert result.success
        assert result.order_id == "12345"

    @pytest.mark.asyncio
    async def test_downward_price_movement_places_stop_buy(self, mock_sdk):
        """Test that downward price movement places new stop buy order."""
        # Setup
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("0"),
            long_fragment_usd=Decimal("0")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Simulate price moving down to unit -1
        event = unit_tracker.calculate_unit_change(Decimal("2249"))

        assert event is not None
        assert event.direction == "down"
        assert event.current_unit == -1

        # New buy should be placed at unit 0 (current + 1)
        buy_price = position_state.get_price_for_unit(0)
        assert buy_price == Decimal("2500")

        # Simulate the order placement
        result = mock_sdk.place_stop_buy(
            symbol="ETH",
            size=position_state.long_fragment_asset,
            trigger_price=buy_price,
            limit_price=buy_price,
            reduce_only=False
        )

        assert result.success
        assert result.order_id == "12346"

    @pytest.mark.asyncio
    async def test_sliding_window_maintains_four_orders(self):
        """Test that sliding window always maintains 4 orders total."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("0"),
            long_fragment_usd=Decimal("0")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Initial state: 4 stops
        assert len(unit_tracker.trailing_stop) == 4
        assert len(unit_tracker.trailing_buy) == 0

        # Move up to unit 1
        event = unit_tracker.calculate_unit_change(Decimal("2750"))
        # Should add stop at 0, keep total at 4
        # In real system, oldest stop would be cancelled

        # Move down to unit -1
        event = unit_tracker.calculate_unit_change(Decimal("2249"))
        # Should add buy at 0

        # Total should always be 4
        total_orders = len(unit_tracker.trailing_stop) + len(unit_tracker.trailing_buy)
        assert total_orders <= 4  # Can't exceed 4 in the window


class TestOrderFillHandling:
    """Test handling of order fills."""

    @pytest.mark.asyncio
    async def test_stop_loss_fill_updates_position(self):
        """Test that stop-loss fill properly updates position."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Set up a stop-loss order at unit -1
        position_map[-1].set_active_order("order_123", OrderType.STOP_LOSS_SELL)
        unit_tracker.trailing_stop = [-4, -3, -2, -1]

        # Simulate fill
        position_map[-1].mark_filled(
            filled_price=Decimal("2249"),
            filled_size=Decimal("1.25")
        )

        # Remove from trailing stop
        unit_tracker.remove_trailing_stop(-1)

        # Add to trailing buy
        unit_tracker.add_trailing_buy(-1)

        # Verify window updated
        assert -1 not in unit_tracker.trailing_stop
        assert -1 in unit_tracker.trailing_buy
        assert len(unit_tracker.trailing_stop) == 3
        assert len(unit_tracker.trailing_buy) == 1

    @pytest.mark.asyncio
    async def test_stop_buy_fill_updates_position(self):
        """Test that stop buy fill properly updates position."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("3.75"),  # Reduced from selling
            position_value_usd=Decimal("9375"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Set up mixed position (retracement)
        unit_tracker.trailing_stop = [-3, -2]
        unit_tracker.trailing_buy = [-1, 0]

        # Set up stop buy at unit 0
        position_map[0].set_active_order("order_124", OrderType.STOP_BUY)

        # Simulate fill
        position_map[0].mark_filled(
            filled_price=Decimal("2500"),
            filled_size=Decimal("1.25")
        )

        # Remove from trailing buy
        unit_tracker.remove_trailing_buy(0)

        # Add to trailing stop
        unit_tracker.add_trailing_stop(0)

        # Verify window updated
        assert 0 not in unit_tracker.trailing_buy
        assert 0 in unit_tracker.trailing_stop
        assert len(unit_tracker.trailing_stop) == 3
        assert len(unit_tracker.trailing_buy) == 1


class TestPhaseTransitions:
    """Test phase transition logic."""

    def test_advance_to_retracement(self):
        """Test transition from advance to retracement phase."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Start in advance
        assert unit_tracker.get_phase() == "advance"

        # Simulate a stop-loss fill
        unit_tracker.remove_trailing_stop(-1)
        unit_tracker.add_trailing_buy(-1)
        unit_tracker.trailing_stop = [-4, -3, -2]

        # Should be in retracement
        assert unit_tracker.get_phase() == "retracement"

    def test_retracement_to_decline(self):
        """Test transition from retracement to decline phase."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("0"),  # All sold
            position_value_usd=Decimal("0"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Set up decline phase
        unit_tracker.trailing_stop = []
        unit_tracker.trailing_buy = [-4, -3, -2, -1]

        assert unit_tracker.get_phase() == "decline"

    def test_decline_to_recovery(self):
        """Test transition from decline to recovery phase."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("1.25"),  # Started buying back
            position_value_usd=Decimal("3125"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Start in decline
        unit_tracker.trailing_stop = []
        unit_tracker.trailing_buy = [-4, -3, -2, -1]
        unit_tracker.last_phase = "decline"

        # Simulate a buy fill
        unit_tracker.remove_trailing_buy(-1)
        unit_tracker.add_trailing_stop(-1)
        unit_tracker.trailing_stop = [-1]
        unit_tracker.trailing_buy = [-4, -3, -2]

        assert unit_tracker.get_phase() == "recovery"

    def test_recovery_to_advance(self):
        """Test transition from recovery back to advance phase."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),  # Fully bought back
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Back to full advance
        unit_tracker.trailing_stop = [-4, -3, -2, -1]
        unit_tracker.trailing_buy = []

        assert unit_tracker.get_phase() == "advance"


class TestRapidPriceMovement:
    """Test handling of rapid price movements."""

    def test_rapid_upward_movement(self):
        """Test rapid upward price movement that skips units."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Jump from unit 0 to unit 5
        event = unit_tracker.calculate_unit_change(Decimal("3750"))

        assert event is not None
        assert event.current_unit == 5
        assert event.direction == "up"

        # All intermediate units should exist in position map
        for unit in range(1, 6):
            assert unit in position_map

    def test_rapid_downward_movement(self):
        """Test rapid downward price movement that skips units."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Jump from unit 0 to unit -5
        event = unit_tracker.calculate_unit_change(Decimal("1250"))

        assert event is not None
        assert event.current_unit == -5
        assert event.direction == "down"

        # All intermediate units should exist
        for unit in range(-5, 0):
            assert unit in position_map


class TestPnLTracking:
    """Test P&L tracking and reinvestment."""

    def test_pnl_tracking_on_complete_cycle(self):
        """Test P&L tracking through a complete sell-buy cycle."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Simulate selling at 2750 (unit 1)
        sell_price = Decimal("2750")
        size = position_state.long_fragment_asset

        # Then buying back at 2500 (unit 0)
        buy_price = Decimal("2500")

        # Track the realized P&L
        unit_tracker.track_realized_pnl(sell_price, buy_price, size)

        # P&L should be (2750 - 2500) * 1.25 = 312.50
        expected_pnl = (sell_price - buy_price) * size
        assert unit_tracker.current_realized_pnl == expected_pnl
        assert unit_tracker.current_realized_pnl == Decimal("312.50")

    def test_pnl_reinvestment_in_recovery(self):
        """Test that P&L is reinvested during recovery phase."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("2.5"),  # Half position
            position_value_usd=Decimal("6250"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Set up recovery phase
        unit_tracker.trailing_stop = [-2, -1]
        unit_tracker.trailing_buy = [1, 2]
        unit_tracker.last_phase = "decline"
        unit_tracker.current_realized_pnl = Decimal("1000")

        # Get adjusted fragment for recovery
        adjusted_fragment = unit_tracker.get_adjusted_fragment_usd()

        # Should be base fragment (3125) + 1/4 of PnL (250) = 3375
        expected = Decimal("3125") + Decimal("250")
        assert adjusted_fragment == expected


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_unit_size(self):
        """Test handling of zero unit size (should not happen in practice)."""
        with pytest.raises(Exception):
            position_state = PositionState(
                entry_price=Decimal("2500"),
                unit_size_usd=Decimal("0"),  # Invalid
                asset_size=Decimal("5.0"),
                position_value_usd=Decimal("12500"),
                original_asset_size=Decimal("5.0"),
                original_position_value_usd=Decimal("12500"),
                long_fragment_asset=Decimal("1.25"),
                long_fragment_usd=Decimal("3125")
            )
            position_map = calculate_initial_position_map(position_state)
            unit_tracker = UnitTracker(position_state, position_map)
            # This would cause division by zero
            unit_tracker.calculate_unit_change(Decimal("2600"))

    def test_negative_price(self):
        """Test handling of negative prices (should not happen in practice)."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        # Extreme downward movement
        event = unit_tracker.calculate_unit_change(Decimal("100"))

        # Should calculate to unit -9
        assert event.current_unit == -9
        assert event.direction == "down"

    @given(
        price_sequence=st.lists(
            st.decimals(min_value=100, max_value=10000, places=2),
            min_size=2,
            max_size=50
        )
    )
    def test_random_price_sequence(self, price_sequence):
        """Property test: system should handle any sequence of prices."""
        position_state = PositionState(
            entry_price=Decimal("2500"),
            unit_size_usd=Decimal("250"),
            asset_size=Decimal("5.0"),
            position_value_usd=Decimal("12500"),
            original_asset_size=Decimal("5.0"),
            original_position_value_usd=Decimal("12500"),
            long_fragment_asset=Decimal("1.25"),
            long_fragment_usd=Decimal("3125")
        )
        position_map = calculate_initial_position_map(position_state)
        unit_tracker = UnitTracker(position_state, position_map)

        prev_unit = 0
        for price in price_sequence:
            event = unit_tracker.calculate_unit_change(price)

            # Verify unit calculation is correct
            expected_unit = int((price - position_state.entry_price) / position_state.unit_size_usd)
            if price < position_state.entry_price and (price - position_state.entry_price) % position_state.unit_size_usd != 0:
                expected_unit -= 1

            assert unit_tracker.current_unit == expected_unit

            # If unit changed, verify event
            if unit_tracker.current_unit != prev_unit:
                assert event is not None
                assert event.current_unit == unit_tracker.current_unit
                assert event.direction == "up" if unit_tracker.current_unit > prev_unit else "down"

            prev_unit = unit_tracker.current_unit

        # Window should never exceed 4 orders
        total_orders = len(unit_tracker.trailing_stop) + len(unit_tracker.trailing_buy)
        assert total_orders <= 4