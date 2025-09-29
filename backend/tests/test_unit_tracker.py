"""
Test suite for UnitTracker to verify proper unit boundary detection.
"""

import pytest
from decimal import Decimal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.strategy.unit_tracker import UnitTracker, Direction, UnitChangeEvent


class TestUnitTracker:
    """Test suite for the UnitTracker class."""

    def test_initialization(self):
        """Test that UnitTracker initializes correctly."""
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("100.00")
        )

        assert tracker.unit_size_usd == Decimal("0.50")
        assert tracker.anchor_price == Decimal("100.00")
        assert tracker.current_unit == 0
        assert tracker.previous_unit == 0
        assert tracker.current_direction == Direction.UP
        assert tracker.current_price == Decimal("100.00")

    def test_positive_unit_calculation(self):
        """Test unit calculation for prices above anchor."""
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("100.00")
        )

        # Test various positive movements
        test_cases = [
            (Decimal("100.49"), 0),   # Just below unit 1
            (Decimal("100.50"), 1),   # Exactly unit 1
            (Decimal("100.99"), 1),   # Just below unit 2
            (Decimal("101.00"), 2),   # Exactly unit 2
            (Decimal("101.49"), 2),   # Just below unit 3
            (Decimal("101.50"), 3),   # Exactly unit 3
        ]

        for price, expected_unit in test_cases:
            tracker.update_price(price)
            assert tracker.current_unit == expected_unit, f"Price {price} should be unit {expected_unit}, got {tracker.current_unit}"

    def test_negative_unit_calculation(self):
        """Test unit calculation for prices below anchor - THIS WAS THE BUG!"""
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("100.00")
        )

        # Test various negative movements
        test_cases = [
            (Decimal("99.51"), -1),   # Below unit 0, in unit -1
            (Decimal("99.50"), -1),   # Exactly at boundary of unit -1
            (Decimal("99.01"), -2),   # Below unit -1, in unit -2
            (Decimal("99.00"), -2),   # Exactly at boundary of unit -2
            (Decimal("98.51"), -3),   # Below unit -2, in unit -3
            (Decimal("98.50"), -3),   # Exactly at boundary of unit -3
        ]

        for price, expected_unit in test_cases:
            tracker.update_price(price)
            assert tracker.current_unit == expected_unit, f"Price {price} should be unit {expected_unit}, got {tracker.current_unit}"

    def test_unit_change_events(self):
        """Test that unit change events are properly emitted."""
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("100.00")
        )

        events_received = []

        def on_unit_change(event: UnitChangeEvent):
            events_received.append(event)

        tracker.on_unit_change = on_unit_change

        # Move from unit 0 to unit 1
        event = tracker.update_price(Decimal("100.50"))
        assert event is not None
        assert event.previous_unit == 0
        assert event.current_unit == 1
        assert event.current_direction == Direction.UP
        assert len(events_received) == 1

        # Move from unit 1 to unit -1 (crosses 0)
        event = tracker.update_price(Decimal("99.50"))
        assert event is not None
        assert event.previous_unit == 1
        assert event.current_unit == -1
        assert event.current_direction == Direction.DOWN
        assert len(events_received) == 2

    def test_real_world_scenario_sol(self):
        """Test the exact scenario from the bug report with SOL."""
        # Recreate the scenario from the analysis report
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("208.07")  # Approximate anchor from report
        )

        # Price at $207.85 is below anchor by $0.22, so it's in unit -1 (floor(-0.22/0.50) = floor(-0.44) = -1)
        tracker.update_price(Decimal("207.85"))
        assert tracker.current_unit == -1, "Price $207.85 with anchor $208.07 should be unit -1"

        # Price moves up to $209.07 - should trigger multiple unit changes
        events = []
        def track_event(event):
            events.append(event)
        tracker.on_unit_change = track_event

        # Move to $209.07 (should be unit 2)
        tracker.update_price(Decimal("209.07"))
        assert tracker.current_unit == 2
        assert len(events) == 1  # One event for the jump from -1 to 2
        assert events[0].previous_unit == -1
        assert events[0].current_unit == 2

    def test_unit_price_calculation(self):
        """Test get_unit_price method."""
        tracker = UnitTracker(
            unit_size_usd=Decimal("0.50"),
            anchor_price=Decimal("100.00")
        )

        assert tracker.get_unit_price(0) == Decimal("100.00")
        assert tracker.get_unit_price(1) == Decimal("100.50")
        assert tracker.get_unit_price(2) == Decimal("101.00")
        assert tracker.get_unit_price(-1) == Decimal("99.50")
        assert tracker.get_unit_price(-2) == Decimal("99.00")

    def test_large_unit_sizes(self):
        """Test with larger unit sizes like for BTC."""
        tracker = UnitTracker(
            unit_size_usd=Decimal("100"),
            anchor_price=Decimal("50000")
        )

        # Test movements
        tracker.update_price(Decimal("50099"))  # Still unit 0
        assert tracker.current_unit == 0

        tracker.update_price(Decimal("50100"))  # Unit 1
        assert tracker.current_unit == 1

        tracker.update_price(Decimal("49900"))  # Unit -1
        assert tracker.current_unit == -1

        tracker.update_price(Decimal("49899"))  # Unit -2
        assert tracker.current_unit == -2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])