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
    symbol: str
    is_active: bool = True
    current_price: Decimal = Field(default=Decimal("0.0"))

    # Core Strategy Parameters
    entry_price: Decimal
    unit_value: Decimal
    current_unit: int = Field(default=0)
    leverage: int = Field(default=10)
    # This now represents the margin required for the initial position
    required_margin: Decimal

    # Phase and Peak/Valley Tracking
    current_phase: PhaseType = Field(default="advance")
    peak_unit: Optional[int] = None
    peak_price: Optional[Decimal] = None
    valley_unit: Optional[int] = None
    valley_price: Optional[Decimal] = None

    # Allocation States (in USD)
    long_invested: Decimal = Field(default=Decimal("0.0"))
    long_cash: Decimal = Field(default=Decimal("0.0"))
    hedge_long: Decimal = Field(default=Decimal("0.0"))
    hedge_short: Decimal = Field(default=Decimal("0.0"))

    # PNL Tracking
    realized_pnl: Decimal = Field(default=Decimal("0.0"))
    unrealized_pnl: Decimal = Field(default=Decimal("0.0"))
    
    # Constants
    MIN_TRADE_VALUE: Decimal = Field(default=Decimal("1.0"))
    UNIT_PERCENTAGE: Decimal = Field(default=Decimal("0.05"))


class TradingPlanCreate(BaseModel):
    """
    Model for creating a new trading plan via the API.
    Client specifies the desired position size in USD.
    """
    symbol: str = Field(..., description="The trading symbol, e.g., 'DOGE/USDC'")
    position_size_usd: Decimal = Field(..., gt=0, description="The desired total position size in USD")
    leverage: int = Field(default=10, gt=0, description="The leverage to be used")


class TradingPlanUpdate(BaseModel):
    """
    Model for updating an existing trading plan's state.
    """
    current_phase: Optional[PhaseType] = None
    peak_unit: Optional[int] = None
    peak_price: Optional[Decimal] = None
    valley_unit: Optional[int] = None
    valley_price: Optional[Decimal] = None
    long_invested: Optional[Decimal] = None
    long_cash: Optional[Decimal] = None
    hedge_long: Optional[Decimal] = None
    hedge_short: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
