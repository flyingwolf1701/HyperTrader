"""
Pytest configuration and fixtures for HyperTrader tests.
"""
import asyncio
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest
from hypothesis import strategies as st

from src.strategy.data_models import (
    OrderType, Phase, ExecutionStatus, PositionState,
    PositionConfig, UnitChangeEvent, OrderFillEvent
)
from src.strategy.unit_tracker import UnitTracker

# ============================================================================
# HYPOTHESIS STRATEGIES
# ============================================================================

@st.composite
def decimal_strategy(draw, min_value=0.01, max_value=100000, places=2):
    """Generate valid Decimal values for testing."""
    value = draw(st.floats(min_value=min_value, max_value=max_value, allow_nan=False, allow_infinity=False))
    return Decimal(str(round(value, places)))

@st.composite
def price_strategy(draw):
    """Generate realistic price values."""
    return draw(decimal_strategy(min_value=100, max_value=10000, places=2))

@st.composite
def unit_size_strategy(draw):
    """Generate realistic unit sizes (price movements)."""
    return draw(decimal_strategy(min_value=10, max_value=1000, places=2))

@st.composite
def position_state_strategy(draw):
    """Generate valid PositionState objects."""
    entry_price = draw(price_strategy())
    unit_size_usd = draw(unit_size_strategy())
    original_asset_size = draw(decimal_strategy(min_value=0.1, max_value=100, places=4))
    original_position_value_usd = draw(decimal_strategy(min_value=1000, max_value=100000, places=2))

    return PositionState(
        entry_price=entry_price,
        unit_size_usd=unit_size_usd,
        asset_size=original_asset_size,
        position_value_usd=original_position_value_usd,
        original_asset_size=original_asset_size,
        original_position_value_usd=original_position_value_usd,
        long_fragment_asset=Decimal("0"),  # Will be calculated in __post_init__
        long_fragment_usd=Decimal("0")  # Will be calculated in __post_init__
    )

# ============================================================================
# FIXTURES - Position and Configuration
# ============================================================================

@pytest.fixture
def sample_position_state():
    """Create a sample PositionState for testing."""
    return PositionState(
        entry_price=Decimal("2500.00"),
        unit_size_usd=Decimal("250.00"),
        asset_size=Decimal("5.0"),
        position_value_usd=Decimal("12500.00"),
        original_asset_size=Decimal("5.0"),
        original_position_value_usd=Decimal("12500.00"),
        long_fragment_asset=Decimal("0"),
        long_fragment_usd=Decimal("0")
    )

@pytest.fixture
def position_map(sample_position_state):
    """Create a position map with initial units."""
    from src.strategy.position_map import calculate_initial_position_map
    return calculate_initial_position_map(sample_position_state)

@pytest.fixture
def unit_tracker(sample_position_state, position_map):
    """Create a UnitTracker instance."""
    return UnitTracker(sample_position_state, position_map)

# ============================================================================
# FIXTURES - Mock Exchange/SDK
# ============================================================================

@pytest.fixture
def mock_sdk():
    """Create a mock HyperliquidClient."""
    sdk = Mock()

    # Setup default behaviors
    sdk.get_current_price.return_value = Decimal("2500.00")
    sdk.get_balance.return_value = Mock(
        total_value=Decimal("10000.00"),
        margin_used=Decimal("2500.00"),
        available=Decimal("7500.00")
    )
    sdk.get_positions.return_value = {}
    sdk.get_open_orders.return_value = []

    # Order operations return success by default
    sdk.place_stop_order.return_value = Mock(
        success=True,
        order_id="12345",
        filled_size=Decimal("0"),
        average_price=Decimal("2500.00"),
        error_message=None
    )
    sdk.place_stop_buy.return_value = Mock(
        success=True,
        order_id="12346",
        filled_size=Decimal("0"),
        average_price=Decimal("2500.00"),
        error_message=None
    )
    sdk.cancel_order.return_value = True
    sdk.cancel_all_orders.return_value = 0

    return sdk

@pytest.fixture
def async_mock_sdk(mock_sdk):
    """Create an async version of the mock SDK."""
    # Convert sync mock to async where needed
    async_sdk = Mock(spec=mock_sdk)
    for attr_name in dir(mock_sdk):
        if not attr_name.startswith('_'):
            attr = getattr(mock_sdk, attr_name)
            if callable(attr):
                setattr(async_sdk, attr_name, Mock(return_value=attr.return_value))
    return async_sdk

# ============================================================================
# FIXTURES - Mock WebSocket
# ============================================================================

@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket client."""
    ws = AsyncMock()

    ws.is_connected = True
    ws.connect = AsyncMock(return_value=True)
    ws.disconnect = AsyncMock()
    ws.subscribe_to_trades = AsyncMock(return_value=True)
    ws.subscribe_to_user_fills = AsyncMock(return_value=True)

    # Price callbacks storage
    ws.price_callbacks = {}
    ws.fill_callbacks = {}

    return ws

# ============================================================================
# FIXTURES - Trading Bot Components
# ============================================================================

@pytest.fixture
def mock_order_manager(mock_sdk, mock_websocket, sample_position_state, position_map, unit_tracker):
    """Create a mock order manager with all dependencies."""
    from src.core.order_manager import OrderManager

    # Create order manager with mocked dependencies
    manager = OrderManager(
        symbol="ETH",
        sdk=mock_sdk,
        position_state=sample_position_state,
        position_map=position_map,
        unit_tracker=unit_tracker,
        testnet=True
    )

    return manager

# ============================================================================
# FIXTURES - Test Data
# ============================================================================

@pytest.fixture
def sample_orders():
    """Sample order data for testing."""
    return [
        {
            "oid": "123",
            "coin": "ETH",
            "side": "B",
            "limitPx": "2500.00",
            "sz": "1.25",
            "orderType": {"trigger": {"triggerPx": "2500.00", "tpsl": "sl"}}
        },
        {
            "oid": "124",
            "coin": "ETH",
            "side": "A",
            "limitPx": "2750.00",
            "sz": "1.25",
            "orderType": {"trigger": {"triggerPx": "2750.00", "tpsl": "sl"}}
        }
    ]

@pytest.fixture
def sample_fill_event():
    """Sample fill event for testing."""
    return {
        "coin": "ETH",
        "px": "2525.00",
        "sz": "-1.25",  # Negative for sell
        "side": "A",
        "oid": "125",
        "time": int(datetime.now().timestamp() * 1000)
    }

# ============================================================================
# FIXTURES - Async Support
# ============================================================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_position_config(unit: int, price: Decimal, order_type: Optional[OrderType] = None) -> PositionConfig:
    """Helper to create a PositionConfig."""
    config = PositionConfig(unit=unit, price=price)
    if order_type:
        config.set_active_order(f"order_{unit}", order_type)
    return config

def simulate_price_movement(unit_tracker: UnitTracker, new_price: Decimal) -> Optional[UnitChangeEvent]:
    """Helper to simulate price movement and get unit change event."""
    return unit_tracker.calculate_unit_change(new_price)

def create_mock_order_result(success: bool = True, order_id: str = "12345") -> Mock:
    """Helper to create a mock order result."""
    return Mock(
        success=success,
        order_id=order_id if success else None,
        filled_size=Decimal("0"),
        average_price=Decimal("2500.00"),
        error_message=None if success else "Order failed"
    )