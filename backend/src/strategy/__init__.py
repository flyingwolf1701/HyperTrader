"""Strategy components for sliding window trading"""

# Import from new data models
from .data_models import (
    OrderType,
    Phase,
    ExecutionStatus,
    PositionState,
    PositionConfig,
    WindowState,
    UnitChangeEvent,
    OrderFillEvent,
    CompoundGrowthMetrics
)

# Import from strategy engine
from .strategy_engine import LongWalletStrategy

# Import from order manager
from .order_manager import OrderManager

# Import from position tracker
from .position_tracker import PositionTracker

# Import from position map (utility functions)
from .position_map import (
    calculate_initial_position_map,
    add_unit_level,
    get_active_orders,
    get_filled_orders,
    get_window_orders,
    get_orders_by_type,
    cancel_all_active_orders,
    # Deprecated functions kept for backward compatibility
    update_sliding_window,
    handle_order_replacement
)

# Import from unit tracker (for backward compatibility)
from .unit_tracker import UnitTracker, SlidingWindow

# Import from config
from .config import LongWalletConfig, TestnetConfig, MainnetConfig

__all__ = [
    # Data models
    'OrderType',
    'Phase',
    'ExecutionStatus',
    'PositionState',
    'PositionConfig',
    'WindowState',
    'UnitChangeEvent',
    'OrderFillEvent',
    'CompoundGrowthMetrics',
    # Strategy components
    'LongWalletStrategy',
    'OrderManager',
    'PositionTracker',
    # Position map functions
    'calculate_initial_position_map',
    'add_unit_level',
    'get_active_orders',
    'get_filled_orders',
    'get_window_orders',
    'get_orders_by_type',
    'cancel_all_active_orders',
    # Backward compatibility
    'update_sliding_window',
    'handle_order_replacement',
    'UnitTracker',
    'SlidingWindow',
    # Config
    'LongWalletConfig',
    'TestnetConfig',
    'MainnetConfig'
]