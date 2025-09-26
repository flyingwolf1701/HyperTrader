"""
Shared data models and configuration for the grid trading strategy.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from enum import Enum


class StrategyState(Enum):
    """Strategy operational states"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    WHIPSAW_DETECTED = "whipsaw_detected"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class StrategyConfig:
    """Configuration for the grid trading strategy"""
    # Asset configuration
    symbol: str
    leverage: int
    position_value_usd: Decimal  # Total position value in USD (what user specifies)
    unit_size_usd: Decimal  # USD per unit movement

    # Exchange settings
    mainnet: bool = False  # Default to testnet
    strategy: str = "long"  # Strategy type (long/short)

    def __post_init__(self):
        """Calculate derived values after initialization"""
        # These are calculated properties, not stored fields
        pass

    @property
    def margin_required(self) -> Decimal:
        """Margin required for the position"""
        return self.position_value_usd / Decimal(self.leverage)

    @property
    def position_fragment_usd(self) -> Decimal:
        """USD value of each fragment (1/4 of total position)"""
        return self.position_value_usd / 4


@dataclass
class StrategyMetrics:
    """Real-time metrics for the strategy"""
    initial_position_value_usd: Decimal
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    current_position_size: Decimal = Decimal("0")
    current_position_value: Decimal = Decimal("0")
    avg_entry_price: Optional[Decimal] = None

    @property
    def total_pnl(self) -> Decimal:
        """Total PnL (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def win_rate(self) -> float:
        """Win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def updated_position_value(self) -> Decimal:
        """Position value including realized PnL for compounding"""
        return self.initial_position_value_usd + self.realized_pnl

    @property
    def new_buy_fragment(self) -> Decimal:
        """Dynamically calculated buy fragment size with compounding"""
        return self.updated_position_value / 4