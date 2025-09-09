"""
Position Map Data Structure - Separated into Static Config and Dynamic State
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
    Static configuration that remains the same for all unit levels.
    These values are set once and don't change during the strategy cycle.
    """
    entry_price: Decimal                # The average price we paid for our asset
    unit_value_usd: Decimal             # USD price movement per unit
    asset_size: Decimal                 # Total amount of asset we purchased
    position_value_usd: Decimal         # Total USD value of the position --- not sure if we need this
    long_fragment_usd: Decimal          # 25% of position value in USD. Hyperliquid will give us this price when we sell our first fragment in retracement
    long_fragment_asset: Decimal        # 25% of asset_size 
    short_fragment_usd: Decimal         # 25% of position value in USD. Hyperliquid will give us this price when we exit our first short fragment in Recovery
    short_fragment_asset: Decimal       # 25% of asset_size only calulated after we have go fully short. 
    
    def __post_init__(self):
        """Calculate fragments after initialization"""
        self.long_fragment_asset = self.asset_size / Decimal("4")

    def get_price_for_unit(self, unit: int) -> Decimal:
        """Calculate price for any unit level"""
        if unit == 0:
            return self.entry_price
        return self.entry_price + (Decimal(unit) * self.unit_value_usd)


@dataclass
class PositionConfig:
    """
    Dynamic state that changes per unit level and during execution.
    These values track orders, execution, and real-time state.
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
    unit_value_usd: Decimal,
    asset_size: Decimal,
    position_value_usd: Decimal
) -> tuple[PositionConfig, Dict[int, PositionState]]:
    """
    Calculate initial position map with unit levels from -10 to +10.
    
    Args:
        entry_price: Entry price for unit 0
        unit_value_usd: USD price movement per unit
        asset_size: The actual amount of asset we purchased
        position_value_usd: Total USD value of the position
        
    Returns:
        Tuple of (PositionConfig, Dict[unit -> PositionState])
    """
    # Create static configuration
    config = PositionState(
        entry_price=entry_price,
        unit_value_usd=unit_value_usd,
        asset_size=asset_size,
        position_value_usd=position_value_usd,
        long_fragment_asset=Decimal("0"),  # Will be calculated in __post_init__
        short_fragment_usd=Decimal("0")  # Will be calculated in __post_init__
    )
    
    # Create position states for each unit level
    position_states = {}
    for unit in range(-10, 11):  # -10 to +10 inclusive
        unit_price = config.get_price_for_unit(unit)
        position_states[unit] = PositionState(unit=unit, price=unit_price)
    
    print(f"📍 Position map created: Entry ${entry_price}, Unit size ${unit_value_usd}")
    print(f"🔒 Fragments: Long={config.long_fragment_asset:.6f} asset, Short=${config.short_fragment_usd:.2f} USD")
    print(f"📊 Range: ${position_states[-10].price:.2f} to ${position_states[10].price:.2f}")
    
    return config, position_states


def add_unit_level(
    config: PositionConfig,
    position_states: Dict[int, PositionState],
    new_unit: int
) -> bool:
    """
    Add a new unit level to the position states (for peaks or valleys).
    
    Args:
        config: Static position configuration
        position_states: Existing position states dictionary
        new_unit: The new unit number to add (positive for peaks, negative for valleys)
        
    Returns:
        True if successful, False if unit already exists
    """
    # Check if unit already exists
    if new_unit in position_states:
        print(f"⚠️  Unit {new_unit} already exists in position map")
        return False
    
    # Calculate price for the new unit using config
    unit_price = config.get_price_for_unit(new_unit)
    
    # Create new position state
    new_state = PositionMap(unit=new_unit, price=unit_price)
    
    # Add to position states
    position_states[new_unit] = new_state
    
    # Dynamic logging based on unit type
    unit_type = "PEAK" if new_unit > 0 else "VALLEY"
    emoji = "🎯" if new_unit > 0 else "📉"
    print(f"{emoji} New {unit_type} unit added: Unit {new_unit} at ${unit_price:.2f}")
    return True