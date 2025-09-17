"""
Comprehensive tests for position_map.py functions.
"""
import pytest
from decimal import Decimal
from hypothesis import given, strategies as st

from src.strategy.data_models import (
    OrderType, ExecutionStatus, PositionState, PositionConfig
)
from src.strategy.position_map import (
    calculate_initial_position_map,
    add_unit_level,
    get_active_orders,
    get_filled_orders,
    get_orders_by_type,
    cancel_all_active_orders
)


class TestPositionMapInitialization:
    """Test position map initialization."""

    def test_calculate_initial_position_map(self, sample_position_state):
        """Test creation of initial position map."""
        position_map = calculate_initial_position_map(sample_position_state)

        # Should create units from -5 to 5
        assert len(position_map) == 11
        assert all(unit in position_map for unit in range(-5, 6))

        # Unit 0 should be at entry price
        assert position_map[0].unit == 0
        assert position_map[0].price == sample_position_state.entry_price

        # Check price calculations
        for unit in range(-5, 6):
            expected_price = sample_position_state.entry_price + (unit * sample_position_state.unit_size_usd)
            assert position_map[unit].price == expected_price
            assert position_map[unit].unit == unit
            assert not position_map[unit].is_active

    @given(
        entry_price=st.decimals(min_value=100, max_value=10000, places=2),
        unit_size=st.decimals(min_value=10, max_value=1000, places=2)
    )
    def test_calculate_initial_position_map_properties(self, entry_price, unit_size):
        """Property-based test for position map initialization."""
        state = PositionState(
            entry_price=entry_price,
            unit_size_usd=unit_size,
            asset_size=Decimal("1"),
            position_value_usd=entry_price,
            original_asset_size=Decimal("1"),
            original_position_value_usd=entry_price,
            long_fragment_asset=Decimal("0.25"),
            long_fragment_usd=entry_price / 4
        )

        position_map = calculate_initial_position_map(state)

        # Verify all units are correctly priced
        for unit, config in position_map.items():
            expected_price = entry_price + (unit * unit_size)
            assert config.price == expected_price
            assert config.unit == unit
            assert config.order_ids == []
            assert not config.is_active


class TestAddUnitLevel:
    """Test adding new unit levels to position map."""

    def test_add_new_unit(self, sample_position_state, position_map):
        """Test adding a new unit level."""
        # Add unit 10 (beyond initial range)
        add_unit_level(sample_position_state, position_map, 10)

        assert 10 in position_map
        assert position_map[10].unit == 10
        expected_price = sample_position_state.entry_price + (10 * sample_position_state.unit_size_usd)
        assert position_map[10].price == expected_price

    def test_add_existing_unit_no_change(self, sample_position_state, position_map):
        """Test that adding existing unit doesn't change it."""
        # Set up unit 0 with an order
        position_map[0].set_active_order("order_123", OrderType.STOP_LOSS_SELL)

        # Try to add unit 0 again
        add_unit_level(sample_position_state, position_map, 0)

        # Should preserve existing data
        assert position_map[0].order_id == "order_123"
        assert position_map[0].is_active

    def test_add_negative_unit(self, sample_position_state, position_map):
        """Test adding negative unit levels."""
        # Add unit -10
        add_unit_level(sample_position_state, position_map, -10)

        assert -10 in position_map
        expected_price = sample_position_state.entry_price + (-10 * sample_position_state.unit_size_usd)
        assert position_map[-10].price == expected_price


class TestGetActiveOrders:
    """Test retrieving active orders from position map."""

    def test_get_active_orders_empty(self, position_map):
        """Test with no active orders."""
        active = get_active_orders(position_map)
        assert active == {}

    def test_get_active_orders_single(self, position_map):
        """Test with single active order."""
        position_map[-1].set_active_order("order_123", OrderType.STOP_LOSS_SELL)

        active = get_active_orders(position_map)

        assert len(active) == 1
        assert -1 in active
        assert active[-1] == position_map[-1]

    def test_get_active_orders_multiple(self, position_map):
        """Test with multiple active orders."""
        position_map[-2].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].set_active_order("order_2", OrderType.STOP_LOSS_SELL)
        position_map[1].set_active_order("order_3", OrderType.STOP_BUY)
        position_map[2].set_active_order("order_4", OrderType.STOP_BUY)

        active = get_active_orders(position_map)

        assert len(active) == 4
        assert all(unit in active for unit in [-2, -1, 1, 2])

    def test_get_active_orders_mixed_states(self, position_map):
        """Test with mix of active, filled, and cancelled orders."""
        # Active order
        position_map[-1].set_active_order("order_1", OrderType.STOP_LOSS_SELL)

        # Filled order
        position_map[0].set_active_order("order_2", OrderType.MARKET_BUY)
        position_map[0].mark_filled()

        # Cancelled order
        position_map[1].set_active_order("order_3", OrderType.STOP_BUY)
        position_map[1].mark_cancelled()

        active = get_active_orders(position_map)

        assert len(active) == 1
        assert -1 in active
        assert 0 not in active  # Filled
        assert 1 not in active  # Cancelled


class TestGetFilledOrders:
    """Test retrieving filled orders from position map."""

    def test_get_filled_orders_empty(self, position_map):
        """Test with no filled orders."""
        filled = get_filled_orders(position_map)
        assert filled == {}

    def test_get_filled_orders_single(self, position_map):
        """Test with single filled order."""
        position_map[0].set_active_order("order_123", OrderType.MARKET_BUY)
        position_map[0].mark_filled()

        filled = get_filled_orders(position_map)

        assert len(filled) == 1
        assert 0 in filled
        assert filled[0] == position_map[0]

    def test_get_filled_orders_with_history(self, position_map):
        """Test filled orders with order history."""
        # Unit with multiple orders in history
        position_map[-1].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].mark_filled()
        position_map[-1].set_active_order("order_2", OrderType.STOP_BUY)
        position_map[-1].mark_cancelled()
        position_map[-1].set_active_order("order_3", OrderType.STOP_LOSS_SELL)
        position_map[-1].mark_filled()

        filled = get_filled_orders(position_map)

        # Should be included since last order is filled
        assert -1 in filled
        assert position_map[-1].execution_status == ExecutionStatus.FILLED


class TestGetOrdersByType:
    """Test filtering orders by type."""

    def test_get_orders_by_type_empty(self, position_map):
        """Test with no orders of specified type."""
        stops = get_orders_by_type(position_map, OrderType.STOP_LOSS_SELL)
        assert stops == {}

    def test_get_orders_by_type_stop_sells(self, position_map):
        """Test getting stop-loss sell orders."""
        position_map[-2].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].set_active_order("order_2", OrderType.STOP_LOSS_SELL)
        position_map[1].set_active_order("order_3", OrderType.STOP_BUY)

        stops = get_orders_by_type(position_map, OrderType.STOP_LOSS_SELL)

        assert len(stops) == 2
        assert -2 in stops
        assert -1 in stops
        assert 1 not in stops

    def test_get_orders_by_type_stop_buys(self, position_map):
        """Test getting stop buy orders."""
        position_map[-1].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[1].set_active_order("order_2", OrderType.STOP_BUY)
        position_map[2].set_active_order("order_3", OrderType.STOP_BUY)

        buys = get_orders_by_type(position_map, OrderType.STOP_BUY)

        assert len(buys) == 2
        assert 1 in buys
        assert 2 in buys
        assert -1 not in buys

    def test_get_orders_by_type_includes_filled(self, position_map):
        """Test that filled orders of correct type are included."""
        position_map[-1].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].mark_filled()

        stops = get_orders_by_type(position_map, OrderType.STOP_LOSS_SELL)

        # Filled orders should still be included when filtering by type
        assert -1 in stops


class TestCancelAllActiveOrders:
    """Test cancelling all active orders."""

    def test_cancel_all_empty(self, position_map):
        """Test cancelling with no active orders."""
        cancelled = cancel_all_active_orders(position_map)
        assert cancelled == []

    def test_cancel_all_single(self, position_map):
        """Test cancelling single active order."""
        position_map[0].set_active_order("order_123", OrderType.STOP_BUY)

        cancelled = cancel_all_active_orders(position_map)

        assert cancelled == [0]
        assert not position_map[0].is_active
        assert position_map[0].execution_status == ExecutionStatus.CANCELLED

    def test_cancel_all_multiple(self, position_map):
        """Test cancelling multiple active orders."""
        position_map[-2].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].set_active_order("order_2", OrderType.STOP_LOSS_SELL)
        position_map[1].set_active_order("order_3", OrderType.STOP_BUY)
        position_map[2].set_active_order("order_4", OrderType.STOP_BUY)

        cancelled = cancel_all_active_orders(position_map)

        assert len(cancelled) == 4
        assert set(cancelled) == {-2, -1, 1, 2}

        # All should be cancelled
        for unit in cancelled:
            assert not position_map[unit].is_active
            assert position_map[unit].execution_status == ExecutionStatus.CANCELLED

    def test_cancel_all_preserves_filled(self, position_map):
        """Test that filled orders are not affected by cancel all."""
        # Set up filled order
        position_map[0].set_active_order("order_1", OrderType.MARKET_BUY)
        position_map[0].mark_filled()

        # Set up active order
        position_map[1].set_active_order("order_2", OrderType.STOP_BUY)

        cancelled = cancel_all_active_orders(position_map)

        assert cancelled == [1]
        assert position_map[0].execution_status == ExecutionStatus.FILLED  # Unchanged
        assert position_map[1].execution_status == ExecutionStatus.CANCELLED


class TestPositionMapIntegration:
    """Integration tests for position map functions."""

    def test_full_order_lifecycle(self, sample_position_state):
        """Test complete order lifecycle through position map."""
        position_map = calculate_initial_position_map(sample_position_state)

        # Place some orders
        position_map[-2].set_active_order("order_1", OrderType.STOP_LOSS_SELL)
        position_map[-1].set_active_order("order_2", OrderType.STOP_LOSS_SELL)

        # Verify active orders
        active = get_active_orders(position_map)
        assert len(active) == 2

        # Fill one order
        position_map[-2].mark_filled()

        # Verify states
        active = get_active_orders(position_map)
        filled = get_filled_orders(position_map)
        assert len(active) == 1
        assert len(filled) == 1

        # Cancel remaining
        cancelled = cancel_all_active_orders(position_map)
        assert cancelled == [-1]

        # Final state
        active = get_active_orders(position_map)
        assert len(active) == 0

    @given(
        num_units=st.integers(min_value=1, max_value=20),
        order_types=st.lists(
            st.sampled_from(list(OrderType)),
            min_size=1,
            max_size=20
        )
    )
    def test_position_map_consistency(self, sample_position_state, num_units, order_types):
        """Property: position map operations should maintain consistency."""
        position_map = calculate_initial_position_map(sample_position_state)

        # Add units and orders
        for i, order_type in enumerate(order_types[:num_units]):
            unit = i - 5  # Start from -5
            if unit not in position_map:
                add_unit_level(sample_position_state, position_map, unit)
            position_map[unit].set_active_order(f"order_{i}", order_type)

        # Verify consistency
        active = get_active_orders(position_map)
        assert len(active) <= num_units

        # Cancel all
        cancelled = cancel_all_active_orders(position_map)
        assert len(cancelled) == len(active)

        # Verify all cancelled
        active_after = get_active_orders(position_map)
        assert len(active_after) == 0