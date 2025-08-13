"""Position sizing calculations for risk management."""

from typing import Dict, Any
from ..settings import settings


class PositionSizing:
    """Calculate position sizes based on risk management rules."""
    
    def __init__(self):
        self.max_drawdown_percent = settings.max_drawdown_percent
        self.default_leverage = settings.default_leverage
    
    def calculate_position_size(
        self, 
        account_balance: float, 
        allocation_percent: float,
        leverage: int = None
    ) -> float:
        """
        Calculate position size based on account balance and allocation.
        
        Args:
            account_balance: Total account balance
            allocation_percent: Percentage of account to allocate (0-100)
            leverage: Leverage to use (default from settings)
            
        Returns:
            Position size in base currency
        """
        if leverage is None:
            leverage = self.default_leverage
        
        # Calculate base allocation
        base_allocation = account_balance * (allocation_percent / 100)
        
        # Apply leverage
        position_size = base_allocation * leverage
        
        return round(position_size, 6)
    
    def calculate_max_loss(self, position_size: float, entry_price: float) -> float:
        """Calculate maximum loss based on 23% drawdown limit."""
        max_loss_percent = self.max_drawdown_percent / 100
        return position_size * entry_price * max_loss_percent
    
    def calculate_stop_loss_price(self, entry_price: float, position_high: float) -> float:
        """Calculate stop loss price to limit drawdown to 23%."""
        if position_high <= entry_price:
            # No gains yet, stop loss at entry minus 23%
            return entry_price * (1 - self.max_drawdown_percent / 100)
        
        # Stop loss at 23% below current high
        gain = position_high - entry_price
        max_retracement = gain * (self.max_drawdown_percent / 100)
        return position_high - max_retracement
    
    def validate_position_size(self, position_size: float, max_position_value: float) -> bool:
        """Validate position size doesn't exceed maximum allowed."""
        return position_size <= max_position_value


# Global position sizing instance
position_sizing = PositionSizing()
