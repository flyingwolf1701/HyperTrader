"""Dynamic stop loss management with trailing functionality."""

from typing import Dict, Any, Optional
from ..settings import settings


class StopLossManager:
    """Manages dynamic and trailing stop losses."""
    
    def __init__(self):
        self.trailing_percent = settings.stop_loss_trailing_percent
    
    def calculate_trailing_stop(
        self, 
        entry_price: float, 
        current_high: float,
        current_stop: Optional[float] = None
    ) -> float:
        """
        Calculate trailing stop loss price.
        
        Args:
            entry_price: Original entry price
            current_high: Current highest price reached
            current_stop: Current stop loss price
            
        Returns:
            New stop loss price
        """
        # Calculate trailing stop based on current high
        trailing_stop = current_high * (1 - self.trailing_percent / 100)
        
        # Never move stop loss down (only up for long positions)
        if current_stop is not None:
            trailing_stop = max(trailing_stop, current_stop)
        
        # Never set stop above entry price initially
        if current_high <= entry_price:
            return entry_price * (1 - self.trailing_percent / 100)
        
        return round(trailing_stop, 6)
    
    def should_update_stop(
        self, 
        current_price: float, 
        current_high: float, 
        current_stop: float
    ) -> bool:
        """Check if stop loss should be updated."""
        new_stop = self.calculate_trailing_stop(current_price, current_high, current_stop)
        return new_stop > current_stop
    
    def calculate_fibonacci_stop(
        self, 
        entry_price: float, 
        position_high: float, 
        fibonacci_level: float = 0.23
    ) -> float:
        """Calculate stop loss based on Fibonacci retracement level."""
        if position_high <= entry_price:
            return entry_price * (1 - fibonacci_level)
        
        gain = position_high - entry_price
        retracement = gain * fibonacci_level
        return position_high - retracement
    
    def get_stop_loss_distance(self, entry_price: float, stop_price: float) -> float:
        """Calculate distance from entry to stop as percentage."""
        if entry_price <= 0:
            return 0.0
        
        return abs((entry_price - stop_price) / entry_price) * 100


# Global stop loss manager instance
stop_loss_manager = StopLossManager()
