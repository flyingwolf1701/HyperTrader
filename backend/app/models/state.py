# backend/app/models/state.py

import logging
from decimal import Decimal
from typing import Literal, Optional, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PhaseType = Literal["advance", "retracement", "decline", "recovery"]


class SystemState(BaseModel):
    """
    Represents the complete state of the trading system for a single symbol.
    """
    symbol: str = "ETH"
    is_active: bool = False
    current_price: Decimal = Field(default=Decimal("0.0"))

    # Core Strategy Parameters
    entry_price: Decimal = Field(default=Decimal("3500.0"))
    unit_value: Decimal = Field(default=Decimal("10.0"))
    current_unit: int = Field(default=0)
    leverage: int = Field(default=10)

    # Phase and Peak/Valley Tracking
    current_phase: PhaseType = Field(default="advance")
    peak_unit: Optional[int] = None
    peak_price: Optional[Decimal] = None
    valley_unit: Optional[int] = None
    valley_price: Optional[Decimal] = None

    # Allocation States (in USD)
    long_invested: Decimal = Field(default=Decimal("500.0"))
    long_cash: Decimal = Field(default=Decimal("0.0"))
    hedge_long: Decimal = Field(default=Decimal("500.0"))
    hedge_short: Decimal = Field(default=Decimal("0.0"))

    # PNL and Reset Tracking
    initial_portfolio_value: Decimal = Field(default=Decimal("1000.0"))
    realized_pnl: Decimal = Field(default=Decimal("0.0"))
    reset_threshold_pnl_percentage: Decimal = Field(default=Decimal("100.0"))
    choppy_markets_count: int = Field(default=0)
    
    # Constants
    MIN_TRADE_VALUE: Decimal = Field(default=Decimal("1.0"))
    UNIT_PERCENTAGE: Decimal = Field(default=Decimal("0.05"))

    def get_total_portfolio_value(self) -> Decimal:
        return self.long_invested + self.long_cash + self.hedge_long + self.hedge_short

    def is_reset_condition_met(self) -> bool:
        if self.initial_portfolio_value == 0:
            return False
        profit_target = self.initial_portfolio_value * (self.reset_threshold_pnl_percentage / 100)
        return self.realized_pnl >= profit_target

    def is_choppy_trading_active(self) -> bool:
        return self.choppy_markets_count > 0
        
    def update_from_model(self, data: 'SystemState') -> None:
        """Helper to update the current model from another model instance."""
        if data is None:
            return
        for key, value in data.model_dump().items():
            setattr(self, key, value)

# Create a single, global instance of the SystemState.
system_state = SystemState()


# --- ADD THESE MISSING CLASSES ---

class TradingPlanBase(BaseModel):
    """Base model for a trading plan, used for creation and updates."""
    symbol: str = Field(..., description="The trading symbol, e.g., 'ETH'")
    entry_price: Decimal = Field(..., description="The initial entry price for the strategy")
    initial_portfolio_value: Decimal = Field(..., description="The starting capital in USD")
    leverage: int = Field(default=10, gt=0, description="The leverage to be used")

class TradingPlanCreate(TradingPlanBase):
    """Model for creating a new trading plan via the API."""
    pass

class TradingPlanUpdate(BaseModel):
    """Model for updating an existing trading plan via the API."""
    is_active: Optional[bool] = None
    leverage: Optional[int] = Field(None, gt=0)

# ------------------------------------
