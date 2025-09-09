"""
Position Map Data Structure - Fixed Architecture
Separates static position config from per-unit dynamic state
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict
from enum import Enum


class OrderType(Enum):
    """Types of orders that can be placed"""
    LIMIT_SELL = "limit_sell"
    LIMIT_BUY = "limit_buy"
    LIMIT_SHORT = "limit_short"
    LIMIT_COVER = "limit_cover"


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
    """
    unit: int
    price: Decimal
    
    # Order management
    order_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    is_active: bool = False
    
    # Execution tracking
    executed_at: Optional[datetime] = None
    executed_price: Optional[Decimal] = None
    executed_size: Optional[Decimal] = None
    
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
        print(f"✅ Unit {self.unit} filled: {executed_size} @ ${executed_price}")
    
    def mark_cancelled(self):
        """Mark this unit's order as cancelled"""
        self.execution_status = ExecutionStatus.CANCELLED
        self.is_active = False
        self.order_id = None
        self.order_type = None
    
    def set_active_order(self, order_id: str, order_type: OrderType):
        """Set an active order for this unit"""
        self.order_id = order_id
        self.order_type = order_type
        self.is_active = True
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
    
    print(f"📍 Position map created: Entry ${entry_price}, Unit size ${unit_size_usd}")
    print(f"🔒 Fragments: Long={position_state.long_fragment_asset:.6f} asset (USD TBD from first sale)")
    print(f"📊 Range: ${position_map[-unit_range].price:.2f} to ${position_map[unit_range].price:.2f}")
    
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
        print(f"⚠️  Unit {new_unit} already exists in position map")
        return False
    
    # Calculate price for the new unit using position_state
    unit_price = calculate_price_for_unit(position_state, new_unit)
    
    # Create new position config for this unit
    new_config = PositionConfig(unit=new_unit, price=unit_price)
    
    # Add to position map
    position_map[new_unit] = new_config
    
    # Dynamic logging based on unit type
    unit_type = "PEAK" if new_unit > 0 else "VALLEY"
    emoji = "🎯" if new_unit > 0 else "📉"
    print(f"{emoji} New {unit_type} unit added: Unit {new_unit} at ${unit_price:.2f}")
    return True


def get_active_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units with active orders"""
    return {unit: config for unit, config in position_map.items() if config.is_active}


def get_filled_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units that have been filled"""
    return {unit: config for unit, config in position_map.items() 
            if config.execution_status == ExecutionStatus.FILLED}


def cancel_all_active_orders(position_map: Dict[int, PositionConfig]):
    """Cancel all active orders in the position map"""
    for unit, config in position_map.items():
        if config.is_active:
            mark_unit_cancelled(position_map, unit)
            print(f"🚫 Cancelled order for unit {unit}")


# Example usage:
if __name__ == "__main__":
    # Initialize position map
    entry_price = Decimal("4500.00")
    unit_size = Decimal("25.00")
    asset_size = Decimal("1.0")  # 1 ETH
    position_value = Decimal("4500.00")
    
    # Create position map
    pos_map = calculate_initial_position_map(
        entry_price, unit_size, asset_size, position_value
    )
    
    # Create separate position state for fragment tracking
    position_state = PositionState(
        entry_price=entry_price,
        unit_size_usd=unit_size,
        asset_size=asset_size,
        position_value_usd=position_value,
        long_fragment_usd=Decimal("0"),
        long_fragment_asset=Decimal("0"),
        short_fragment_usd=Decimal("0"),
        short_fragment_asset=Decimal("0")
    )
    
    # Example: Set an active order
    set_unit_active_order(pos_map, -1, "order_123", OrderType.LIMIT_SELL)
    
    # Example: Mark an order as filled
    mark_unit_filled(pos_map, -1, Decimal("4475.00"), Decimal("0.25"))
    
    # Example: Add a new peak unit
    add_unit_level(pos_map, entry_price, unit_size, 11)
    
    print(f"Active orders: {len(get_active_orders(pos_map))}")
    print(f"Filled orders: {len(get_filled_orders(pos_map))}")
