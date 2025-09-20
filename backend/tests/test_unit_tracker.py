"""
Comprehensive tests for unit_tracker.py including sliding window management.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from hypothesis import given, assume, strategies as st
from unittest.mock import Mock, patch

from src.strategy.data_models import Phase, PositionState, PositionConfig
from src.strategy.unit_tracker import UnitTracker
from src.strategy.position_map import calculate_initial_position_map


class TestUnitTracker:
    """Test UnitTracker functionality."""

    def test_initialization(self, sample_position_state, position_map):
        """Test UnitTracker initialization."""
        tracker = UnitTracker(sample_position_state, position_map)

        assert tracker.current_unit == 0
        assert tracker.last_phase == "advance"
        assert tracker.trailing_stop == [-4, -3, -2, -1]
        assert tracker.trailing_buy == []
        assert tracker.current_realized_pnl == Decimal(0)

    def test_initialization_without_unit_0(self, sample_position_state):
        """Test that initialization fails without unit 0."""
        invalid_map = {1: PositionConfig(unit=1, price=Decimal("2750"))}

        with pytest.raises(ValueError, match="Unit 0 missing from position map"):
            UnitTracker(sample_position_state, invalid_map)

    # ============================================================================
    # UNIT CALCULATION TESTS
    # ============================================================================

    def test_calculate_unit_no_change(self, unit_tracker):
        """Test that small price movements don't trigger unit changes."""
        # Entry price is 2500, unit size is 250
        # Prices within 2500-2749 should stay at unit 0
        event = unit_tracker.calculate_unit_change(Decimal("2500"))
        assert event is None
        assert unit_tracker.current_unit == 0

        event = unit_tracker.calculate_unit_change(Decimal("2600"))
        assert event is None
        assert unit_tracker.current_unit == 0

        event = unit_tracker.calculate_unit_change(Decimal("2749"))
        assert event is None
        assert unit_tracker.current_unit == 0

    def test_calculate_unit_change_up(self, unit_tracker):
        """Test upward unit crossing."""
        # Entry price is 2500, unit size is 250
        # Price 2750 should trigger unit 1
        event = unit_tracker.calculate_unit_change(Decimal("2750"))

        assert event is not None
        assert event.current_unit == 1
        assert event.direction == "up"
        assert event.phase == Phase.ADVANCE
        assert event.window_composition == "4S/0B"
        assert unit_tracker.current_unit == 1

    def test_calculate_unit_change_down(self, unit_tracker):
        """Test downward unit crossing."""
        # Entry price is 2500, unit size is 250
        # Price 2249 should trigger unit -1
        event = unit_tracker.calculate_unit_change(Decimal("2249"))

        assert event is not None
        assert event.current_unit == -1
        assert event.direction == "down"
        assert event.phase == Phase.ADVANCE  # Still advance with 4 stops
        assert event.window_composition == "4S/0B"
        assert unit_tracker.current_unit == -1

    def test_rapid_price_movement_detection(self, unit_tracker):
        """Test detection of rapid price movements that skip units."""
        # Jump from unit 0 to unit 5 (skip 4 units)
        # Entry price 2500, unit size 250, so 3750 = unit 5
        with patch('src.strategy.unit_tracker.logger') as mock_logger:
            event = unit_tracker.calculate_unit_change(Decimal("3750"))

            assert event is not None
            assert event.current_unit == 5
            assert event.direction == "up"

            # Should log warning about skipped units
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Rapid price movement" in warning_call
            assert "4 units" in warning_call  # Skipped 4 units (1, 2, 3, 4)

    def test_negative_unit_calculation(self, unit_tracker):
        """Test correct calculation of negative units."""
        # Test various negative prices
        # Entry 2500, unit 250

        # Price 2000 = unit -2
        event = unit_tracker.calculate_unit_change(Decimal("2000"))
        assert unit_tracker.current_unit == -2

        # Price 1500 = unit -4
        event = unit_tracker.calculate_unit_change(Decimal("1500"))
        assert unit_tracker.current_unit == -4

        # Price 1000 = unit -6
        event = unit_tracker.calculate_unit_change(Decimal("1000"))
        assert unit_tracker.current_unit == -6

    # ============================================================================
    # PHASE DETECTION TESTS
    # ============================================================================

    def test_phase_advance(self, unit_tracker):
        """Test advance phase detection (4 stops, 0 buys)."""
        assert unit_tracker.get_phase() == "advance"

    def test_phase_decline(self, unit_tracker):
        """Test decline phase detection (0 stops, 4 buys)."""
        unit_tracker.trailing_stop = []
        unit_tracker.trailing_buy = [1, 2, 3, 4]

        assert unit_tracker.get_phase() == "decline"

    def test_phase_retracement(self, unit_tracker):
        """Test retracement phase (mixed, coming from advance)."""
        unit_tracker.trailing_stop = [-2, -1]
        unit_tracker.trailing_buy = [1, 2]
        unit_tracker.last_phase = "advance"

        assert unit_tracker.get_phase() == "retracement"

    def test_phase_recovery(self, unit_tracker):
        """Test recovery phase (mixed, coming from decline)."""
        unit_tracker.trailing_stop = [1, 2]
        unit_tracker.trailing_buy = [3, 4]
        unit_tracker.last_phase = "decline"

        assert unit_tracker.get_phase() == "recovery"

    def test_phase_transitions(self, unit_tracker):
        """Test phase transitions maintain last_phase correctly."""
        # Start in advance
        assert unit_tracker.get_phase() == "advance"
        assert unit_tracker.last_phase == "advance"

        # Transition to retracement
        unit_tracker.trailing_stop = [-2, -1, 0]
        unit_tracker.trailing_buy = [1]
        phase = unit_tracker.get_phase()
        assert phase == "retracement"
        assert unit_tracker.last_phase == "retracement"

        # Continue retracement
        unit_tracker.trailing_stop = [-1, 0]
        unit_tracker.trailing_buy = [1, 2]
        phase = unit_tracker.get_phase()
        assert phase == "retracement"
        assert unit_tracker.last_phase == "retracement"

    # ============================================================================
    # LIST MANAGEMENT TESTS
    # ============================================================================

    def test_add_trailing_stop(self, unit_tracker):
        """Test adding units to trailing stop list."""
        unit_tracker.trailing_stop = []

        assert unit_tracker.add_trailing_stop(-1)
        assert unit_tracker.trailing_stop == [-1]

        assert unit_tracker.add_trailing_stop(-3)
        assert unit_tracker.trailing_stop == [-3, -1]  # Sorted

        assert unit_tracker.add_trailing_stop(-2)
        assert unit_tracker.trailing_stop == [-3, -2, -1]  # Sorted

        # Duplicate should not be added
        assert not unit_tracker.add_trailing_stop(-2)
        assert unit_tracker.trailing_stop == [-3, -2, -1]

    def test_remove_trailing_stop(self, unit_tracker):
        """Test removing units from trailing stop list."""
        unit_tracker.trailing_stop = [-3, -2, -1]

        assert unit_tracker.remove_trailing_stop(-2)
        assert unit_tracker.trailing_stop == [-3, -1]

        assert not unit_tracker.remove_trailing_stop(-2)  # Already removed
        assert unit_tracker.trailing_stop == [-3, -1]

    def test_add_trailing_buy(self, unit_tracker):
        """Test adding units to trailing buy list."""
        assert unit_tracker.add_trailing_buy(1)
        assert unit_tracker.trailing_buy == [1]

        assert unit_tracker.add_trailing_buy(3)
        assert unit_tracker.trailing_buy == [1, 3]  # Sorted

        # Duplicate should not be added
        assert not unit_tracker.add_trailing_buy(1)
        assert unit_tracker.trailing_buy == [1, 3]

    def test_remove_trailing_buy(self, unit_tracker):
        """Test removing units from trailing buy list."""
        unit_tracker.trailing_buy = [1, 2, 3]

        assert unit_tracker.remove_trailing_buy(2)
        assert unit_tracker.trailing_buy == [1, 3]

        assert not unit_tracker.remove_trailing_buy(2)  # Already removed
        assert unit_tracker.trailing_buy == [1, 3]

    # ============================================================================
    # PNL TRACKING TESTS
    # ============================================================================

    def test_track_realized_pnl(self, unit_tracker):
        """Test PnL tracking."""
        # Sell at 2600, bought at 2500, size 1.0
        unit_tracker.track_realized_pnl(
            sell_price=Decimal("2600"),
            buy_price=Decimal("2500"),
            size=Decimal("1.0")
        )

        assert unit_tracker.current_realized_pnl == Decimal("100")

        # Another trade
        unit_tracker.track_realized_pnl(
            sell_price=Decimal("2700"),
            buy_price=Decimal("2600"),
            size=Decimal("0.5")
        )

        assert unit_tracker.current_realized_pnl == Decimal("150")

    def test_get_adjusted_fragment_usd_no_recovery(self, unit_tracker):
        """Test fragment adjustment when not in recovery."""
        unit_tracker.current_realized_pnl = Decimal("1000")

        # In advance phase, no adjustment
        fragment = unit_tracker.get_adjusted_fragment_usd()
        assert fragment == unit_tracker.position_state.long_fragment_usd

    def test_get_adjusted_fragment_usd_in_recovery(self, unit_tracker):
        """Test fragment adjustment during recovery with PnL."""
        # Set up recovery phase
        unit_tracker.trailing_stop = [1, 2]
        unit_tracker.trailing_buy = [3, 4]
        unit_tracker.last_phase = "decline"
        unit_tracker.current_realized_pnl = Decimal("1000")

        fragment = unit_tracker.get_adjusted_fragment_usd()

        # Should add 1/4 of PnL to base fragment
        # Base fragment is 3125 (12500 / 4)
        # PnL per fragment is 250 (1000 / 4)
        expected = Decimal("3125") + Decimal("250")
        assert fragment == expected

    # ============================================================================
    # WINDOW STATE TESTS
    # ============================================================================

    def test_get_window_state(self, unit_tracker):
        """Test window state reporting."""
        state = unit_tracker.get_window_state()

        assert state['current_unit'] == 0
        assert state['phase'] == 'advance'
        assert state['trailing_stop'] == [-4, -3, -2, -1]
        assert state['trailing_buy'] == []
        assert state['total_orders'] == 4
        assert state['current_realized_pnl'] == 0.0

    # ============================================================================
    # PROPERTY-BASED TESTS
    # ============================================================================

    @given(
        current_price=st.decimals(min_value=100, max_value=10000, places=2)
    )
    def test_unit_calculation_consistency(self, sample_position_state, position_map, current_price):
        """Property: unit calculation should be consistent and reversible."""
        tracker = UnitTracker(sample_position_state, position_map)

        # Calculate unit change
        event = tracker.calculate_unit_change(current_price)

        # Verify unit matches mathematical calculation
        price_diff = current_price - sample_position_state.entry_price
        expected_unit = int(price_diff / sample_position_state.unit_size_usd)
        if price_diff < 0 and price_diff % sample_position_state.unit_size_usd != 0:
            expected_unit -= 1

        assert tracker.current_unit == expected_unit

    @given(
        stop_count=st.integers(min_value=0, max_value=4),
        buy_count=st.integers(min_value=0, max_value=4)
    )
    def test_phase_detection_consistency(self, unit_tracker, stop_count, buy_count):
        """Property: phase detection should be deterministic based on list counts."""
        assume(stop_count + buy_count == 4)  # Total should be 4

        # Set up the lists
        unit_tracker.trailing_stop = list(range(stop_count))
        unit_tracker.trailing_buy = list(range(stop_count, stop_count + buy_count))

        phase = unit_tracker.get_phase()

        # Verify phase matches expected
        if stop_count == 4 and buy_count == 0:
            assert phase == "advance"
        elif stop_count == 0 and buy_count == 4:
            assert phase == "decline"
        else:
            assert phase in ["retracement", "recovery"]

    @given(
        sell_prices=st.lists(
            st.decimals(min_value=1000, max_value=5000, places=2),
            min_size=1,
            max_size=10
        ),
        buy_prices=st.lists(
            st.decimals(min_value=1000, max_value=5000, places=2),
            min_size=1,
            max_size=10
        ),
        sizes=st.lists(
            st.decimals(min_value=0.1, max_value=10, places=2),
            min_size=1,
            max_size=10
        )
    )
    def test_pnl_accumulation(self, unit_tracker, sell_prices, buy_prices, sizes):
        """Property: PnL should accumulate correctly."""
        # Ensure lists have same length
        min_len = min(len(sell_prices), len(buy_prices), len(sizes))
        sell_prices = sell_prices[:min_len]
        buy_prices = buy_prices[:min_len]
        sizes = sizes[:min_len]

        total_pnl = Decimal(0)

        for sell, buy, size in zip(sell_prices, buy_prices, sizes):
            pnl = (sell - buy) * size
            total_pnl += pnl
            unit_tracker.track_realized_pnl(sell, buy, size)

        assert unit_tracker.current_realized_pnl == total_pnl


class TestUnitTrackerIntegration:
    """Integration tests for UnitTracker with position map."""

    def test_unit_crossing_updates_position_map(self, sample_position_state):
        """Test that crossing units properly updates the position map."""
        position_map = calculate_initial_position_map(sample_position_state)
        tracker = UnitTracker(sample_position_state, position_map)

        # Cross to unit 1
        event = tracker.calculate_unit_change(Decimal("2750"))

        # Unit 1 should now exist in position map
        assert 1 in position_map
        assert position_map[1].price == Decimal("2750")

    def test_rapid_movement_creates_all_units(self, sample_position_state):
        """Test that rapid price movement creates all intermediate units."""
        position_map = calculate_initial_position_map(sample_position_state)
        tracker = UnitTracker(sample_position_state, position_map)

        # Jump to unit 5
        event = tracker.calculate_unit_change(Decimal("3750"))

        # All units from 1 to 5 should exist
        for unit in range(1, 6):
            assert unit in position_map
            expected_price = sample_position_state.entry_price + (unit * sample_position_state.unit_size_usd)
            assert position_map[unit].price == expected_price