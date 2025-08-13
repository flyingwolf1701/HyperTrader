"""Trading plan data models and schemas."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TradingPlanCreate(BaseModel):
    """Schema for creating a new trading plan."""
    symbol: str = Field(..., description="Trading symbol (e.g., BTC-USD)")
    allocation_percent: float = Field(..., ge=0, le=100, description="Portfolio allocation percentage")
    leverage: int = Field(default=1, ge=1, le=10, description="Leverage multiplier")
    fibonacci_levels: List[float] = Field(default=[0.23, 0.38, 0.50, 0.618])
    stop_loss_percent: float = Field(default=2.0, description="Trailing stop loss percentage")
    max_positions: int = Field(default=3, description="Maximum concurrent positions")
    auto_execute: bool = Field(default=True, description="Enable automatic execution")


class TradingPlan(BaseModel):
    """Trading plan database model."""
    id: int
    symbol: str
    allocation_percent: float
    leverage: int
    fibonacci_levels: List[float]
    stop_loss_percent: float
    max_positions: int
    auto_execute: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TradingPlanUpdate(BaseModel):
    """Schema for updating an existing trading plan."""
    allocation_percent: Optional[float] = Field(None, ge=0, le=100)
    leverage: Optional[int] = Field(None, ge=1, le=10)
    fibonacci_levels: Optional[List[float]] = None
    stop_loss_percent: Optional[float] = None
    max_positions: Optional[int] = None
    auto_execute: Optional[bool] = None
    is_active: Optional[bool] = None


class TradingPlanResponse(BaseModel):
    """Response schema for trading plan API."""
    id: int
    symbol: str
    allocation_percent: float
    leverage: int
    fibonacci_levels: List[float]
    stop_loss_percent: float
    max_positions: int
    auto_execute: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Additional computed fields
    current_positions: int = 0
    unrealized_pnl: float = 0.0
    total_value: float = 0.0
