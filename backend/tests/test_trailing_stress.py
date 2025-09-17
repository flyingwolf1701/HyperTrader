"""
Hypothesis stress test for trailing stop and buy list management.
Tests all possible market movements to ensure correct behavior.
"""
import pytest
from decimal import Decimal
from typing import List, Tuple
from hypothesis import given, strategies as st, assume, settings, example
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant, Bundle

from src.strategy.data_models import PositionState, PositionConfig, Phase
from src.strategy.position_map import calculate_initial_position_map, add_unit_level
from src.strategy.unit_tracker import UnitTracker


class TestTrailingListsStress:
    """Stress test trailing stop and buy list management with hypothesis."""

    @given(
        movements=st.lists(
            st.integers(min_value=-1, max_value=1).filter(lambda x: x != 0),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_random_movements_maintain_invariants(self, movements):
        """Test that random movements maintain trailing list invariants."""
        # Setup with realistic ETH values
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),  # $12,500 / $4,500
            position_value_usd=Decimal("12500"),
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)
        current_unit = 0

        for movement in movements:
            current_unit += movement
            # Ensure we stay within reasonable bounds
            if current_unit < -45 or current_unit > 45:
                current_unit -= movement
                continue

            # Calculate the price for this unit
            price = position_state.get_price_for_unit(current_unit)

            # Trigger unit change
            event = tracker.calculate_unit_change(price)

            # Verify invariants
            self._verify_invariants(tracker, current_unit)

    @given(
        run_length=st.integers(min_value=2, max_value=10),
        direction=st.sampled_from([1, -1])
    )
    @settings(max_examples=50)
    def test_consecutive_runs(self, run_length, direction):
        """Test consecutive movements in one direction."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)
        current_unit = 0

        # Execute the run
        for _ in range(run_length):
            current_unit += direction
            price = position_state.get_price_for_unit(current_unit)
            event = tracker.calculate_unit_change(price)

            # After each movement, verify invariants
            self._verify_invariants(tracker, current_unit)

        # Verify final state
        assert tracker.current_unit == current_unit

    @given(
        oscillations=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_oscillating_movements(self, oscillations):
        """Test up-down-up-down oscillating pattern."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)
        current_unit = 0

        for i in range(oscillations):
            # Move up then down
            direction = 1 if i % 2 == 0 else -1
            current_unit += direction
            price = position_state.get_price_for_unit(current_unit)
            event = tracker.calculate_unit_change(price)

            self._verify_invariants(tracker, current_unit)

    @given(
        jump_size=st.integers(min_value=2, max_value=15)
    )
    @settings(max_examples=30)
    def test_rapid_movements(self, jump_size):
        """Test rapid price movements that skip multiple units."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)

        # Jump up rapidly
        target_unit = jump_size
        price = position_state.get_price_for_unit(target_unit)
        event = tracker.calculate_unit_change(price)

        assert tracker.current_unit == target_unit
        self._verify_invariants(tracker, target_unit)

        # Jump down rapidly
        target_unit = -jump_size
        price = position_state.get_price_for_unit(target_unit)
        event = tracker.calculate_unit_change(price)

        assert tracker.current_unit == target_unit
        self._verify_invariants(tracker, target_unit)

    def _verify_invariants(self, tracker: UnitTracker, current_unit: int):
        """Verify all invariants for trailing lists."""
        # Total orders should never exceed 4
        total_orders = len(tracker.trailing_stop) + len(tracker.trailing_buy)
        assert total_orders <= 4, f"Total orders {total_orders} exceeds 4"

        # Trailing stops should be at or below current unit
        for stop_unit in tracker.trailing_stop:
            assert stop_unit <= current_unit, f"Stop {stop_unit} not at/below current {current_unit}"

        # Trailing buys should be at or above current unit
        for buy_unit in tracker.trailing_buy:
            assert buy_unit >= current_unit, f"Buy {buy_unit} not at/above current {current_unit}"

        # Lists should be sorted
        assert tracker.trailing_stop == sorted(tracker.trailing_stop), "Stops not sorted"
        assert tracker.trailing_buy == sorted(tracker.trailing_buy), "Buys not sorted"

        # No duplicates
        assert len(tracker.trailing_stop) == len(set(tracker.trailing_stop)), "Duplicate stops"
        assert len(tracker.trailing_buy) == len(set(tracker.trailing_buy)), "Duplicate buys"

        # Phase should match list composition
        phase = tracker.get_phase()
        stop_count = len(tracker.trailing_stop)
        buy_count = len(tracker.trailing_buy)

        if stop_count == 4 and buy_count == 0:
            assert phase == "advance", f"Wrong phase: {phase} for 4S/0B"
        elif stop_count == 0 and buy_count == 4:
            assert phase == "decline", f"Wrong phase: {phase} for 0S/4B"
        elif stop_count > 0 and buy_count > 0:
            assert phase in ["retracement", "recovery"], f"Wrong phase: {phase} for mixed"


class TrailingStateMachine(RuleBasedStateMachine):
    """Stateful testing of trailing stop/buy list management."""

    def __init__(self):
        super().__init__()
        # Initialize position and tracker
        self.position_state, self.position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=100  # Large range for testing
        )
        self.tracker = UnitTracker(self.position_state, self.position_map)
        self.current_unit = 0
        self.movement_history = []

    @rule(direction=st.sampled_from([1, -1]))
    def move_one_unit(self, direction):
        """Move up or down by one unit."""
        new_unit = self.current_unit + direction

        # Stay within bounds
        if -40 <= new_unit <= 40:
            self.current_unit = new_unit
            price = self.position_state.get_price_for_unit(self.current_unit)
            event = self.tracker.calculate_unit_change(price)
            self.movement_history.append(direction)

            # Simulate what main.py should do
            if event:
                if event.direction == 'up':
                    # Should place stop at current-1
                    new_stop = event.current_unit - 1
                    if new_stop not in self.tracker.trailing_stop:
                        self.tracker.add_trailing_stop(new_stop)

                    # Maintain total of 4 orders
                    total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)
                    while total > 4:
                        # Remove oldest stop if we have stops, otherwise remove furthest buy
                        if len(self.tracker.trailing_stop) > 0:
                            oldest = min(self.tracker.trailing_stop)
                            self.tracker.remove_trailing_stop(oldest)
                        elif len(self.tracker.trailing_buy) > 0:
                            oldest = max(self.tracker.trailing_buy)
                            self.tracker.remove_trailing_buy(oldest)
                        total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)

                elif event.direction == 'down':
                    # Should place buy at current+1
                    new_buy = event.current_unit + 1
                    if new_buy not in self.tracker.trailing_buy:
                        self.tracker.add_trailing_buy(new_buy)

                    # Maintain total of 4 orders
                    total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)
                    while total > 4:
                        # Remove furthest buy if we have buys, otherwise remove oldest stop
                        if len(self.tracker.trailing_buy) > 0:
                            oldest = max(self.tracker.trailing_buy)
                            self.tracker.remove_trailing_buy(oldest)
                        elif len(self.tracker.trailing_stop) > 0:
                            oldest = min(self.tracker.trailing_stop)
                            self.tracker.remove_trailing_stop(oldest)
                        total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)

    @rule(jump=st.integers(min_value=2, max_value=10))
    def jump_units(self, jump):
        """Jump multiple units at once."""
        # Alternate between up and down jumps
        direction = 1 if len(self.movement_history) % 2 == 0 else -1
        new_unit = self.current_unit + (jump * direction)

        if -40 <= new_unit <= 40:
            self.current_unit = new_unit
            price = self.position_state.get_price_for_unit(self.current_unit)
            event = self.tracker.calculate_unit_change(price)
            self.movement_history.append(jump * direction)

    @rule()
    def simulate_stop_fill(self):
        """Simulate a stop-loss order being filled."""
        # Only simulate fills for stops that could realistically be hit
        # (stops at or above current unit could be triggered)
        valid_stops = [s for s in self.tracker.trailing_stop if s >= self.tracker.current_unit - 1]

        if valid_stops:
            # Fill the highest stop (most likely to be hit)
            filled_stop = max(valid_stops)
            self.tracker.remove_trailing_stop(filled_stop)

            # After selling, we might place a buy order at same level
            # But only if it makes sense relative to current position
            if filled_stop > self.tracker.current_unit:
                self.tracker.add_trailing_buy(filled_stop)

                # Maintain 4 total orders
                total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)
                if total > 4:
                    # Remove furthest buy
                    if len(self.tracker.trailing_buy) > 0:
                        oldest_buy = max(self.tracker.trailing_buy)
                        self.tracker.remove_trailing_buy(oldest_buy)

    @rule()
    def simulate_buy_fill(self):
        """Simulate a buy order being filled."""
        # Only simulate fills for buys that could realistically be hit
        # (buys at or below current unit could be triggered)
        valid_buys = [b for b in self.tracker.trailing_buy if b <= self.tracker.current_unit + 1]

        if valid_buys:
            # Fill the lowest buy (most likely to be hit)
            filled_buy = min(valid_buys)
            self.tracker.remove_trailing_buy(filled_buy)

            # After buying, we might place a stop at same level
            # But only if it makes sense relative to current position
            if filled_buy < self.tracker.current_unit:
                self.tracker.add_trailing_stop(filled_buy)

                # Maintain 4 total orders
                total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)
                if total > 4:
                    # Remove furthest stop
                    if len(self.tracker.trailing_stop) > 0:
                        oldest_stop = min(self.tracker.trailing_stop)
                        self.tracker.remove_trailing_stop(oldest_stop)

    @invariant()
    def check_invariants(self, settings=None, output=None, run_times=None):
        """Check that all invariants hold."""
        # Never more than 4 total orders
        total = len(self.tracker.trailing_stop) + len(self.tracker.trailing_buy)
        assert total <= 4, f"Total orders {total} exceeds 4"

        # Stops at or below current, buys at or above
        for stop in self.tracker.trailing_stop:
            assert stop <= self.tracker.current_unit, f"Stop {stop} above current {self.tracker.current_unit}"

        for buy in self.tracker.trailing_buy:
            assert buy >= self.tracker.current_unit, f"Buy {buy} below current {self.tracker.current_unit}"

        # Lists sorted
        assert self.tracker.trailing_stop == sorted(self.tracker.trailing_stop)
        assert self.tracker.trailing_buy == sorted(self.tracker.trailing_buy)

        # No duplicates
        assert len(set(self.tracker.trailing_stop)) == len(self.tracker.trailing_stop)
        assert len(set(self.tracker.trailing_buy)) == len(self.tracker.trailing_buy)

        # Current unit matches tracker
        assert self.tracker.current_unit == self.current_unit


# Create test case from state machine
TestTrailingStateMachine = TrailingStateMachine.TestCase


class TestSpecificScenarios:
    """Test specific problematic scenarios."""

    def test_initial_state(self):
        """Test the initial state is correct."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)

        # Should start with 4 stops, 0 buys
        assert len(tracker.trailing_stop) == 4
        assert tracker.trailing_stop == [-4, -3, -2, -1]
        assert len(tracker.trailing_buy) == 0
        assert tracker.get_phase() == "advance"

    def test_boundary_movements(self):
        """Test movements at map boundaries."""
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("4500"),
            unit_size_usd=Decimal("25"),
            asset_size=Decimal("2.78"),
            position_value_usd=Decimal("12500"),
            unit_range=10  # Small range to test boundaries
        )

        tracker = UnitTracker(position_state, position_map)

        # Move to upper boundary
        for i in range(1, 10):
            price = position_state.get_price_for_unit(i)
            event = tracker.calculate_unit_change(price)
            assert tracker.current_unit == i

        # Move to lower boundary
        for i in range(9, -10, -1):
            price = position_state.get_price_for_unit(i)
            event = tracker.calculate_unit_change(price)
            assert tracker.current_unit == i

    def test_your_actual_problem(self):
        """Test the scenario from your actual trading history."""
        # Your BTC trade scenario
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("116880"),  # Your BTC entry
            unit_size_usd=Decimal("25"),    # Your unit size
            asset_size=Decimal("0.0214"),   # Your actual position
            position_value_usd=Decimal("2500"),  # Your position value
            unit_range=50
        )

        tracker = UnitTracker(position_state, position_map)

        # Simulate price movements that would create order clustering
        # Price moves within a tight range
        prices = [
            Decimal("116930"),  # Up 2 units
            Decimal("116905"),  # Down 1 unit
            Decimal("116955"),  # Up 2 units
            Decimal("116930"),  # Down 1 unit
            Decimal("116980"),  # Up 2 units
        ]

        for price in prices:
            event = tracker.calculate_unit_change(price)

            # Verify we don't accumulate orders
            total = len(tracker.trailing_stop) + len(tracker.trailing_buy)
            assert total <= 4, f"Orders accumulated to {total}"

            # Log state for debugging
            print(f"Price: {price}, Unit: {tracker.current_unit}")
            print(f"  Stops: {tracker.trailing_stop}")
            print(f"  Buys: {tracker.trailing_buy}")
            print(f"  Phase: {tracker.get_phase()}")
            print()