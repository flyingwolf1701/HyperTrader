"""
Position Map Data Structure - Sliding Window Strategy v9.2.6
Separates static position config from per-unit dynamic state
Supports sliding window order management with 4-order tracking
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict
from enum import Enum
from loguru import logger


class OrderType(Enum):
    """Types of orders that can be placed"""
    LIMIT_SELL = "limit_sell"    # Long wallet sell
    LIMIT_BUY = "limit_buy"      # Long wallet buy
    LIMIT_SHORT = "limit_short"  # Hedge wallet short
    LIMIT_COVER = "limit_cover"  # Hedge wallet cover
    MARKET_SELL = "market_sell"  # Full position exit
    MARKET_BUY = "market_buy"    # Full position entry


class ExecutionStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class PositionState:
    """
    Static configuration that remains the same for the entire strategy cycle.
    These values are set once at position entry and don't change.
    """
    entry_price: Decimal                # The average price we paid for our asset (unit 0)
    unit_size_usd: Decimal             # USD price movement per unit ($5, $25, etc.)
    asset_size: Decimal                # Total amount of asset we purchased
    position_value_usd: Decimal        # Total USD value of the position at entry
    
    # Fragment values (calculated once at peak and locked for entire cycle)
    long_fragment_usd: Decimal         # 25% of position value in USD (for buying)
    long_fragment_asset: Decimal       # 25% of asset_size (for selling)
    short_fragment_usd: Decimal        # 25% of position value in USD (for shorting)
    short_fragment_asset: Decimal      # 25% of short position asset amount (calculated after going short)
    
    def __post_init__(self):
        """Calculate standard fragments after initialization"""
        # Long fragments are always 25% of original position
        self.long_fragment_usd = self.position_value_usd / Decimal("4")
        self.long_fragment_asset = self.asset_size / Decimal("4")
        
        # Short fragments start as same USD value (will be updated during strategy)
        self.short_fragment_usd = self.position_value_usd / Decimal("4")
        # short_fragment_asset will be calculated later when we have short positions

    def get_price_for_unit(self, unit: int) -> Decimal:
        """Calculate price for any unit level"""
        return self.entry_price + (Decimal(unit) * self.unit_size_usd)
    
    def update_short_fragments(self, total_short_position_value: Decimal, total_short_asset_size: Decimal):
        """Update short fragment values based on current short position"""
        self.short_fragment_usd = total_short_position_value / Decimal("4")
        self.short_fragment_asset = total_short_asset_size / Decimal("4")


@dataclass
class PositionConfig:
    """
    Dynamic state per unit level - tracks orders, execution, and real-time state.
    Each unit level gets its own PositionConfig instance.
    Supports sliding window order management.
    """
    unit: int
    price: Decimal
    
    # Order management
    order_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    is_active: bool = False
    
    # Sliding window tracking
    in_window: bool = False  # Is this unit part of the current 4-order window?
    window_position: Optional[int] = None  # Position in window (0-3)
    
    # Execution tracking
    executed_at: Optional[datetime] = None
    executed_price: Optional[Decimal] = None
    executed_size: Optional[Decimal] = None
    execution_count: int = 0  # Track how many times this unit has executed
    
    # Metadata
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def mark_filled(self, executed_price: Decimal, executed_size: Decimal):
        """Mark this unit as filled with execution details"""
        self.execution_status = ExecutionStatus.FILLED
        self.executed_at = datetime.now()
        self.executed_price = executed_price
        self.executed_size = executed_size
        self.is_active = False
        self.in_window = False  # Remove from window when filled
        self.execution_count += 1
        logger.info(f"Unit {self.unit} filled: {executed_size} @ ${executed_price} (execution #{self.execution_count})")
    
    def mark_cancelled(self):
        """Mark this unit's order as cancelled"""
        self.execution_status = ExecutionStatus.CANCELLED
        self.is_active = False
        self.order_id = None
        self.order_type = None
    
    def set_active_order(self, order_id: str, order_type: OrderType, in_window: bool = False):
        """Set an active order for this unit"""
        self.order_id = order_id
        self.order_type = order_type
        self.is_active = True
        self.in_window = in_window
        self.execution_status = ExecutionStatus.PENDING


def calculate_initial_position_map(
    entry_price: Decimal, 
    unit_size_usd: Decimal,
    asset_size: Decimal,
    position_value_usd: Decimal,
    unit_range: int = 10
) -> tuple[PositionState, Dict[int, PositionConfig]]:
    """
    Calculate initial position map with per-unit configurations.
    
    Args:
        entry_price: Entry price for unit 0
        unit_size_usd: USD price movement per unit
        asset_size: The actual amount of asset we purchased
        position_value_usd: Total USD value of the position
        unit_range: How many units above/below to pre-calculate (default: 10)
        
    Returns:
        Tuple of (PositionState, Dict[unit -> PositionConfig])
    """
    # Create static configuration (shared across all units)
    position_state = PositionState(
        entry_price=entry_price,
        unit_size_usd=unit_size_usd,
        asset_size=asset_size,
        position_value_usd=position_value_usd,
        long_fragment_usd=Decimal("0"),    # Will be calculated in __post_init__
        long_fragment_asset=Decimal("0"),  # Will be calculated in __post_init__
        short_fragment_usd=Decimal("0"),   # Will be calculated in __post_init__
        short_fragment_asset=Decimal("0")  # Will be set later during strategy
    )
    
    # Create per-unit configurations
    position_map = {}
    for unit in range(-unit_range, unit_range + 1):  # -10 to +10 inclusive
        unit_price = position_state.get_price_for_unit(unit)
        position_map[unit] = PositionConfig(unit=unit, price=unit_price)
    
    logger.info(f"Position map created: Entry ${entry_price}, Unit size ${unit_size_usd}")
    logger.info(f"Fragments: Long={position_state.long_fragment_asset:.6f} asset (USD TBD from first sale)")
    logger.info(f"Range: ${position_map[-unit_range].price:.2f} to ${position_map[unit_range].price:.2f}")
    
    return position_state, position_map


def add_unit_level(
    position_state: PositionState,
    position_map: Dict[int, PositionConfig],
    new_unit: int
) -> bool:
    """
    Add a new unit level to the position map (for new peaks or valleys).
    
    Args:
        position_state: Static position configuration
        position_map: Existing position map dictionary
        new_unit: The new unit number to add (positive for peaks, negative for valleys)
        
    Returns:
        True if successful, False if unit already exists
    """
    # Check if unit already exists
    if new_unit in position_map:
        logger.warning(f"Unit {new_unit} already exists in position map")
        return False
    
    # Calculate price for the new unit using position_state
    unit_price = position_state.get_price_for_unit(new_unit)
    
    # Create new position config for this unit
    new_config = PositionConfig(unit=new_unit, price=unit_price)
    
    # Add to position map
    position_map[new_unit] = new_config
    
    # Dynamic logging based on unit type
    unit_type = "PEAK" if new_unit > 0 else "VALLEY"
    logger.info(f"New {unit_type} unit added: Unit {new_unit} at ${unit_price:.2f}")
    return True


def get_active_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units with active orders"""
    return {unit: config for unit, config in position_map.items() if config.is_active}


def get_filled_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units that have been filled"""
    return {unit: config for unit, config in position_map.items() 
            if config.execution_status == ExecutionStatus.FILLED}


def get_window_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units that are part of the current sliding window"""
    return {unit: config for unit, config in position_map.items() if config.in_window}


def get_orders_by_type(position_map: Dict[int, PositionConfig], order_type: OrderType) -> Dict[int, PositionConfig]:
    """Get all units with a specific order type"""
    return {unit: config for unit, config in position_map.items() 
            if config.order_type == order_type and config.is_active}


def cancel_all_active_orders(position_map: Dict[int, PositionConfig]):
    """Cancel all active orders in the position map"""
    for unit, config in position_map.items():
        if config.is_active:
            config.mark_cancelled()
            logger.info(f"Cancelled order for unit {unit}")


def update_sliding_window(position_map: Dict[int, PositionConfig], 
                         window_units: list[int],
                         order_type: OrderType):
    """
    Update the sliding window to track specific units.
    
    Args:
        position_map: The position map dictionary
        window_units: List of unit numbers that should be in the window
        order_type: Type of orders in this window
    """
    # Clear current window flags
    for config in position_map.values():
        config.in_window = False
        config.window_position = None
    
    # Set new window
    for i, unit in enumerate(sorted(window_units)):
        if unit in position_map:
            position_map[unit].in_window = True
            position_map[unit].window_position = i
            if not position_map[unit].is_active:
                # Prepare for order placement
                position_map[unit].order_type = order_type
    
    logger.info(f"Window updated: {sorted(window_units)} with {order_type.value} orders")


def handle_order_replacement(position_map: Dict[int, PositionConfig],
                           executed_unit: int,
                           current_unit: int,
                           order_type: str) -> Optional[int]:
    """
    Handle order replacement logic per v9.2.6 strategy.
    When an order executes, place the opposite type at the appropriate unit.
    
    Args:
        position_map: The position map dictionary
        executed_unit: Unit where order executed
        current_unit: Current price unit
        order_type: 'sell' or 'buy' that executed
    
    Returns:
        Unit number where replacement order should be placed
    """
    if order_type == 'sell':
        # Sell executed -> place buy at current+1
        replacement_unit = current_unit + 1
        replacement_type = OrderType.LIMIT_BUY
    elif order_type == 'buy':
        # Buy executed -> place sell at current-1
        replacement_unit = current_unit - 1
        replacement_type = OrderType.LIMIT_SELL
    else:
        return None
    
    # Ensure the replacement unit exists in map
    if replacement_unit not in position_map:
        from .position_map import add_unit_level
        # This would need the position_state passed in
        logger.warning(f"Need to add unit {replacement_unit} to position map")
        return None
    
    # Mark the replacement unit for order placement
    position_map[replacement_unit].order_type = replacement_type
    position_map[replacement_unit].in_window = True
    
    logger.info(f"Order replacement: {order_type} at unit {executed_unit} -> {replacement_type.value} at unit {replacement_unit}")
    return replacement_unit


# Example usage:
if __name__ == "__main__":
    # Initialize position map
    entry_price = Decimal("4500.00")
    unit_size = Decimal("25.00")
    asset_size = Decimal("1.0")  # 1 ETH
    position_value = Decimal("4500.00")
    
    # Create position map with sliding window support
    position_state, position_map = calculate_initial_position_map(
        entry_price, unit_size, asset_size, position_value
    )
    
    # Example: Initialize sliding window with 4 sell orders
    initial_window = [-4, -3, -2, -1]
    update_sliding_window(position_map, initial_window, OrderType.LIMIT_SELL)
    
    # Example: Set active orders for the window
    for unit in initial_window:
        position_map[unit].set_active_order(f"order_{unit}", OrderType.LIMIT_SELL, in_window=True)
    
    # Example: Simulate order execution and replacement
    executed_unit = -1
    current_unit = 0
    position_map[executed_unit].mark_filled(Decimal("4475.00"), Decimal("0.25"))
    
    # Handle order replacement
    replacement_unit = handle_order_replacement(
        position_map, executed_unit, current_unit, 'sell'
    )
    
    print(f"\nWindow orders: {len(get_window_orders(position_map))}")
    print(f"Active orders: {len(get_active_orders(position_map))}")
    print(f"Filled orders: {len(get_filled_orders(position_map))}")
    print(f"Sell orders: {len(get_orders_by_type(position_map, OrderType.LIMIT_SELL))}")
    print(f"Buy orders: {len(get_orders_by_type(position_map, OrderType.LIMIT_BUY))}")
