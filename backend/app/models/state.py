"""System state model for HyperTrader."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class SystemState(BaseModel):
    """Current system state for trading strategy."""
    
    # Core tracking variables
    entry_price: float
    current_price: float
    current_unit: int
    peak_unit: Optional[int]
    valley_unit: Optional[int]
    
    # Allocation amounts
    long_invested: float
    long_cash: float
    hedge_long: float
    hedge_short: float
    
    # Configuration
    leverage: int
    unit_price: float
    symbol: str
    
    # Metadata
    phase: str  # ADVANCE, RETRACEMENT, DECLINE, RECOVERY
    is_choppy: bool
    last_updated: datetime
    
    @property
    def total_portfolio(self) -> float:
        """Calculate total portfolio value."""
        return self.long_invested + self.long_cash + self.hedge_long + self.hedge_short
    
    @property
    def long_allocation_percent(self) -> float:
        """Calculate long allocation percentage."""
        long_total = self.long_invested + self.long_cash
        if long_total == 0:
            return 0
        return (self.long_invested / long_total) * 100
    
    @property
    def hedge_long_percent(self) -> float:
        """Calculate hedge long percentage."""
        hedge_total = self.hedge_long + self.hedge_short
        if hedge_total == 0:
            return 0
        return (self.hedge_long / hedge_total) * 100
