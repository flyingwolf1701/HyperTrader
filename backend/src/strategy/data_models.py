"""
Data Models for HyperTrader Long Wallet Strategy
Pure data structures with no business logic
"""

from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict


class OrderType(Enum):
    """Types of orders used in the long wallet strategy"""
    STOP_LOSS_SELL = "stop_loss_sell"  # Stop-loss for long positions
    LIMIT_BUY = "limit_buy"            # Limit buy order
    MARKET_BUY = "market_buy"          # Market buy for entry
    MARKET_SELL = "market_sell"        # Market sell for emergency


class Phase(Enum):
    """Trading phases based on order composition"""
    ADVANCE = "advance"          # 100% long, all stop-losses
    RETRACEMENT = "retracement"  # Mixed position, mix of orders
    DECLINE = "decline"          # 100% cash, all limit buys
    RECOVER = "recover"          # Mixed position returning to long
    RESET = "reset"             # Transitioning to new cycle


class ExecutionStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class PositionState:
    """
    Static configuration that remains mostly the same for the strategy cycle.
    Fragments are recalculated on RESET.
    """
    # Core position data
    entry_price: Decimal                # The price we entered at (unit 0)
    unit_size_usd: Decimal              # USD price movement per unit
    asset_size: Decimal                 # Current amount of asset we have
    position_value_usd: Decimal         # Current USD value of the position
    
    # Original values for fragment calculation (updated on RESET)
    original_asset_size: Decimal        # Asset amount at cycle start
    original_position_value_usd: Decimal # USD value at cycle start
    
    # Fragments (25% each) - recalculated on RESET
    long_fragment_asset: Decimal        # For stop-loss sells (25% of asset)
    long_fragment_usd: Decimal          # For limit buys (25% of USD value)
    
    # Cycle tracking for RESET and compound growth
    cycle_number: int = 0
    cycle_start_value: Decimal = field(default_factory=lambda: Decimal("0"))
    cumulative_growth: Decimal = field(default_factory=lambda: Decimal("1.0"))
    
    def __post_init__(self):
        """Calculate fragments if not provided"""
        if self.long_fragment_asset == Decimal("0"):
            self.long_fragment_asset = self.original_asset_size / Decimal("4")
        if self.long_fragment_usd == Decimal("0"):
            self.long_fragment_usd = self.original_position_value_usd / Decimal("4")
    
    def get_price_for_unit(self, unit: int) -> Decimal:
        """Calculate price for any unit level"""
        return self.entry_price + (Decimal(unit) * self.unit_size_usd)
    
    def update_for_reset(self, new_asset_size: Decimal, new_position_value: Decimal):
        """Update position state for new cycle after RESET"""
        # Track growth
        growth_this_cycle = new_position_value / self.original_position_value_usd
        self.cumulative_growth *= growth_this_cycle
        self.cycle_number += 1
        
        # Update baseline
        self.original_asset_size = new_asset_size
        self.original_position_value_usd = new_position_value
        self.asset_size = new_asset_size
        self.position_value_usd = new_position_value
        
        # Recalculate fragments for new cycle
        self.long_fragment_asset = new_asset_size / Decimal("4")
        self.long_fragment_usd = new_position_value / Decimal("4")


@dataclass
class WindowState:
    """Tracks the two order windows for long wallet strategy"""
    stop_loss_orders: List[int] = field(default_factory=list)  # Units with stop-losses
    limit_buy_orders: List[int] = field(default_factory=list)  # Units with limit buys
    
    def total_orders(self) -> int:
        """Total number of active orders across both windows"""
        return len(self.stop_loss_orders) + len(self.limit_buy_orders)
    
    def is_all_stop_losses(self) -> bool:
        """Check if we have only stop-loss orders (ADVANCE phase)"""
        from .config import LongWalletConfig
        return len(self.stop_loss_orders) == LongWalletConfig.WINDOW_SIZE and len(self.limit_buy_orders) == 0
    
    def is_all_limit_buys(self) -> bool:
        """Check if we have only limit buy orders (DECLINE phase)"""
        from .config import LongWalletConfig
        return len(self.limit_buy_orders) == LongWalletConfig.WINDOW_SIZE and len(self.stop_loss_orders) == 0
    
    def is_mixed(self) -> bool:
        """Check if we have both types (RETRACEMENT/RECOVER phases)"""
        return len(self.stop_loss_orders) > 0 and len(self.limit_buy_orders) > 0
    
    def add_stop_loss(self, unit: int):
        """Add a stop-loss order at unit"""
        if unit not in self.stop_loss_orders:
            self.stop_loss_orders.append(unit)
            self.stop_loss_orders.sort()
    
    def add_limit_buy(self, unit: int):
        """Add a limit buy order at unit"""
        if unit not in self.limit_buy_orders:
            self.limit_buy_orders.append(unit)
            self.limit_buy_orders.sort()
    
    def remove_stop_loss(self, unit: int):
        """Remove a stop-loss order from unit"""
        if unit in self.stop_loss_orders:
            self.stop_loss_orders.remove(unit)
    
    def remove_limit_buy(self, unit: int):
        """Remove a limit buy order from unit"""
        if unit in self.limit_buy_orders:
            self.limit_buy_orders.remove(unit)


@dataclass
class PositionConfig:
    """
    Dynamic state per unit level - tracks orders and execution.
    Used for tracking individual orders at specific price levels.
    """
    unit: int
    price: Decimal
    
    # Order management
    order_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    is_active: bool = False
    
    # Window tracking removed - now using list-based tracking in UnitTracker
    
    # Execution tracking
    executed_at: Optional[datetime] = None
    executed_price: Optional[Decimal] = None
    executed_size: Optional[Decimal] = None
    execution_count: int = 0  # Track how many times this unit has executed
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    def mark_filled(self, executed_price: Decimal, executed_size: Decimal):
        """Mark this unit's order as filled"""
        self.execution_status = ExecutionStatus.FILLED
        self.executed_at = datetime.now()
        self.executed_price = executed_price
        self.executed_size = executed_size
        self.is_active = False
        self.execution_count += 1
    
    def mark_cancelled(self):
        """Mark this unit's order as cancelled"""
        self.execution_status = ExecutionStatus.CANCELLED
        self.is_active = False
        self.order_id = None
        self.order_type = None
    
    def set_active_order(self, order_id: str, order_type: OrderType, in_window: bool = True):
        """Set an active order for this unit"""
        self.order_id = order_id
        self.order_type = order_type
        self.is_active = True
        self.execution_status = ExecutionStatus.PENDING


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


@dataclass
class CompoundGrowthMetrics:
    """Tracks compound growth across cycles"""
    initial_value: Decimal
    current_value: Decimal
    total_cycles: int
    cumulative_growth: Decimal
    average_growth_per_cycle: Decimal
    best_cycle_growth: Decimal
    worst_cycle_growth: Decimal
    current_cycle_start_value: Decimal
    
    def calculate_current_cycle_growth(self) -> Decimal:
        """Calculate growth for current incomplete cycle"""
        if self.current_cycle_start_value > 0:
            return self.current_value / self.current_cycle_start_value
        return Decimal("1.0")