"""Position tracking data models and schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class PositionStatus(str, Enum):
    """Position status enumeration."""
    OPEN = "open"
    HEDGED = "hedged"
    SCALED = "scaled"
    CLOSED = "closed"


class PositionType(str, Enum):
    """Position type enumeration."""
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"


class PositionCreate(BaseModel):
    """Schema for creating a new position."""
    trading_plan_id: int
    symbol: str
    position_type: PositionType
    size: float = Field(..., gt=0, description="Position size")
    entry_price: float = Field(..., gt=0, description="Entry price")
    leverage: int = Field(default=1, ge=1, le=10)
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


class Position(BaseModel):
    """Position database model."""
    id: int
    trading_plan_id: int
    symbol: str
    position_type: PositionType
    status: PositionStatus
    size: float
    entry_price: float
    exit_price: Optional[float]
    current_price: float
    highest_price: float
    leverage: int
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    unrealized_pnl: float
    realized_pnl: Optional[float]
    hedge_position_id: Optional[int]  # Reference to hedge position
    parent_position_id: Optional[int]  # Reference to original position if this is a hedge
    opened_at: datetime
    closed_at: Optional[datetime]
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PositionUpdate(BaseModel):
    """Schema for updating position data."""
    current_price: Optional[float] = None
    highest_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    status: Optional[PositionStatus] = None
