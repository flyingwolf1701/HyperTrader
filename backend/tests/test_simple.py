"""
Simple tests to verify the core functionality works.
These tests match the actual implementation.
"""
import pytest
from decimal import Decimal
from src.strategy.data_models import OrderType, Phase, ExecutionStatus, PositionState, PositionConfig
from src.strategy.position_map import calculate_initial_position_map, add_unit_level
from src.strategy.unit_tracker import UnitTracker

# Testing with Eth numbers
def test_position_state_creation():
    """Test that we can create a PositionState."""
    state = PositionState(
        entry_price=Decimal("2500"), 
        unit_size_usd=Decimal("250"), # should be 25 not 250. This strategy would fail at that unit_size
        asset_size=Decimal("5"), 
        position_value_usd=Decimal("12500"),
        original_asset_size=Decimal("5"),
        original_position_value_usd=Decimal("12500"),
        long_fragment_asset=Decimal("0"),
        long_fragment_usd=Decimal("0")
    )

    # Fragments should be calculated
    assert state.long_fragment_asset == Decimal("1.25")  # 5 / 4
    assert state.long_fragment_usd == Decimal("3125")  # 12500 / 4

    # Price calculation
    assert state.get_price_for_unit(0) == Decimal("2500")
    assert state.get_price_for_unit(1) == Decimal("2750")
    assert state.get_price_for_unit(-1) == Decimal("2250")


def test_position_config_order_tracking():
    """Test that PositionConfig tracks orders correctly."""
    config = PositionConfig(unit=0, price=Decimal("2500"))

    # Initial state
    assert not config.is_active
    assert config.order_id is None

    # Set active order
    config.set_active_order("order_123", OrderType.STOP_LOSS_SELL)
    assert config.is_active
    assert config.order_id == "order_123"
    assert config.order_type == OrderType.STOP_LOSS_SELL
    assert config.execution_status == ExecutionStatus.PENDING

    # Mark filled
    config.mark_filled()
    assert not config.is_active
    assert config.execution_status == ExecutionStatus.FILLED

    # Order history preserved
    assert len(config.order_ids) == 1
    assert config.order_ids[0] == "order_123"


def test_position_map_creation():
    """Test creating initial position map."""
    # This matches the actual function signature
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500"),
        unit_range=5
    )

    # Check position state
    assert position_state.entry_price == Decimal("2500")
    assert position_state.unit_size_usd == Decimal("250")

    # Check position map has correct range
    # With unit_range=5, we get -5 to 5 (11 units)
    assert len(position_map) == 11
    assert 0 in position_map
    assert -5 in position_map
    assert 5 in position_map

    # Check prices
    assert position_map[0].price == Decimal("2500")
    assert position_map[1].price == Decimal("2750")
    assert position_map[-1].price == Decimal("2250")


def test_unit_tracker_initialization():
    """Test UnitTracker initialization."""
    # Create position state and map
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500"),
        unit_range=5
    )

    # Create unit tracker
    tracker = UnitTracker(position_state, position_map)

    # Check initial state
    assert tracker.current_unit == 0
    assert tracker.last_phase == "advance"
    assert tracker.trailing_stop == [-4, -3, -2, -1]
    assert tracker.trailing_buy == []
    assert tracker.current_realized_pnl == Decimal("0")


def test_unit_tracker_calculate_unit_change():
    """Test unit change calculation."""
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500"),
        unit_range=10
    )

    tracker = UnitTracker(position_state, position_map)

    # No change within same unit
    event = tracker.calculate_unit_change(Decimal("2600"))
    assert event is None
    assert tracker.current_unit == 0

    # Cross to unit 1
    event = tracker.calculate_unit_change(Decimal("2750"))
    assert event is not None
    assert event.current_unit == 1
    assert event.direction == "up"
    assert tracker.current_unit == 1

    # Cross down (from unit 1 to -2 is a big jump)
    event = tracker.calculate_unit_change(Decimal("2249"))
    assert event is not None
    assert event.current_unit == -2  # Actually unit -2 from unit 1
    assert event.direction == "down"
    assert tracker.current_unit == -2


def test_unit_tracker_phase_detection():
    """Test phase detection."""
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500")
    )

    tracker = UnitTracker(position_state, position_map)

    # Initial advance phase
    assert tracker.get_phase() == "advance"

    # Retracement phase
    tracker.trailing_stop = [-3, -2, -1]
    tracker.trailing_buy = [0]
    tracker.last_phase = "advance"
    assert tracker.get_phase() == "retracement"

    # Decline phase
    tracker.trailing_stop = []
    tracker.trailing_buy = [-2, -1, 0, 1]
    assert tracker.get_phase() == "decline"

    # Recovery phase
    tracker.trailing_stop = [0]
    tracker.trailing_buy = [-2, -1, 1]
    tracker.last_phase = "decline"
    assert tracker.get_phase() == "recovery"


def test_unit_tracker_list_management():
    """Test trailing list management."""
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500")
    )

    tracker = UnitTracker(position_state, position_map)

    # Clear and test adding stops
    tracker.trailing_stop = []
    assert tracker.add_trailing_stop(-2)
    assert tracker.add_trailing_stop(-1)
    assert tracker.trailing_stop == [-2, -1]

    # Duplicate not added
    assert not tracker.add_trailing_stop(-1)
    assert tracker.trailing_stop == [-2, -1]

    # Remove stop
    assert tracker.remove_trailing_stop(-2)
    assert tracker.trailing_stop == [-1]

    # Add buy
    assert tracker.add_trailing_buy(1)
    assert tracker.trailing_buy == [1]

    # Remove buy
    assert tracker.remove_trailing_buy(1)
    assert tracker.trailing_buy == []


def test_unit_tracker_pnl():
    """Test PnL tracking."""
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500")
    )

    tracker = UnitTracker(position_state, position_map)

    # Track a profitable trade
    tracker.track_realized_pnl(
        sell_price=Decimal("2600"),
        buy_price=Decimal("2500"),
        size=Decimal("1")
    )

    assert tracker.current_realized_pnl == Decimal("100")

    # Track another trade
    tracker.track_realized_pnl(
        sell_price=Decimal("2700"),
        buy_price=Decimal("2600"),
        size=Decimal("2")
    )

    assert tracker.current_realized_pnl == Decimal("300")  # 100 + 200


def test_rapid_price_movement():
    """Test handling of rapid price movements."""
    position_state, position_map = calculate_initial_position_map(
        entry_price=Decimal("2500"),
        unit_size_usd=Decimal("250"),
        asset_size=Decimal("5"),
        position_value_usd=Decimal("12500"),
        unit_range=10
    )

    tracker = UnitTracker(position_state, position_map)

    # Jump multiple units
    event = tracker.calculate_unit_change(Decimal("3500"))  # Jump to unit 4

    assert event is not None
    assert event.current_unit == 4
    assert tracker.current_unit == 4

    # Units 1, 2, 3, 4 should all exist now
    for unit in range(1, 5):
        assert unit in position_map