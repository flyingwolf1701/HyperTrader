"""
Most of these are horrible! AI should be ashamed of writing such crap!
"""

from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict


class OrderType(Enum):
    """Types of orders used in the long wallet strategy"""
    STOP_LOSS_SELL = "stop_sell"       # Stop order to sell (on way down)
    STOP_BUY = "stop_buy"              # Stop order to buy (on way up)
    MARKET_BUY = "market_buy"          # Market buy for entry
    MARKET_SELL = "market_sell"        # Market sell for emergency


class Phase(Enum):
    """Trading phases based on order composition (simplified for v10)"""
    FULL_POSITION = "full_position"  # 4 sells, 0 buys (100% position)
    MIXED = "mixed"                  # Mix of sells and buys
    FULL_CASH = "full_cash"          # 0 sells, 4 buys (100% cash)


class ExecutionStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class PositionState:
    """
    Simple position configuration as per data_flow.md.
    Tracks position data and fragments for the sliding window strategy.
    """
    # Core position data
    entry_price: Decimal                # The price we entered at (unit 0)
    unit_size_usd: Decimal              # USD price movement per unit
    asset_size: Decimal                 # Current amount of asset we have
    position_value_usd: Decimal         # Current USD value of the position

    # Original values for fragment calculation
    original_asset_size: Decimal        # Asset amount at start
    original_position_value_usd: Decimal # USD value at start

    # Fragments (25% each)
    long_fragment_asset: Decimal        # For stop-loss sells (25% of asset)
    long_fragment_usd: Decimal          # For limit buys (25% of USD value)

    def __post_init__(self):
        """Calculate fragments if not provided"""
        if self.long_fragment_asset == Decimal("0"):
            self.long_fragment_asset = self.original_asset_size / Decimal("4")
        if self.long_fragment_usd == Decimal("0"):
            self.long_fragment_usd = self.original_position_value_usd / Decimal("4")

    def get_price_for_unit(self, unit: int) -> Decimal:
        """Calculate price for any unit level"""
        return self.entry_price + (Decimal(unit) * self.unit_size_usd)


@dataclass
class PositionConfig:
    """
    Simple per-unit tracking as per data_flow.md.
    Tracks order history at each price level.
    """
    unit: int
    price: Decimal

    # Order management - Lists to track history as per data_flow.md
    order_ids: List[str] = field(default_factory=list)
    order_types: List[OrderType] = field(default_factory=list)
    order_statuses: List[ExecutionStatus] = field(default_factory=list)
    is_active: bool = False  # Current order active status

    def mark_filled(self, filled_price: Optional[Decimal] = None, filled_size: Optional[Decimal] = None):
        """Mark this unit's order as filled

        Args:
            filled_price: The actual fill price (optional, for logging)
            filled_size: The actual fill size (optional, for logging)
        """
        # Update the last order status to FILLED
        if self.order_statuses:
            self.order_statuses[-1] = ExecutionStatus.FILLED
        self.is_active = False

    def mark_cancelled(self):
        """Mark this unit's order as cancelled"""
        # Update the last order status to CANCELLED
        if self.order_statuses:
            self.order_statuses[-1] = ExecutionStatus.CANCELLED
        self.is_active = False

    def set_active_order(self, order_id: str, order_type: OrderType):
        """Set an active order for this unit - appends to history"""
        # Append to lists as per data_flow.md
        self.order_ids.append(order_id)
        self.order_types.append(order_type)
        self.order_statuses.append(ExecutionStatus.PENDING)
        self.is_active = True

   

@dataclass
class UnitChangeEvent:
    """Event triggered when unit boundary is crossed"""
    price: Decimal
    phase: Phase
    current_unit: int
    timestamp: datetime
    direction: str  # 'up' or 'down'
    window_composition: str  # e.g., "4S/0B" for 4 stops, 0 buys


@dataclass
class OrderFillEvent:
    """Event triggered when an order is filled"""
    order_id: str
    order_type: OrderType
    unit: int
    filled_price: Decimal
    filled_size: Decimal
    timestamp: datetime
    phase_before: Phase
    phase_after: Optional[Phase] = None


