"""Fibonacci retracement calculations for position-relative levels."""

import numpy as np
from typing import Dict, List
from ..settings import settings


class FibonacciCalculator:
    """Calculate position-relative Fibonacci levels for hedging strategy."""
    
    def __init__(self):
        self.fibonacci_levels = settings.fibonacci_levels
    
    def calculate_retracements(self, entry_price: float, position_high: float) -> Dict[str, float]:
        """
        Calculate Fibonacci retracement levels based on position gains.
        
        Args:
            entry_price: Original entry price of the position
            position_high: Highest price reached since entry
            
        Returns:
            Dictionary with retracement levels and their prices
        """
        if position_high <= entry_price:
            # No gains yet, return entry price for all levels
            return {f"{int(level*100)}%": entry_price for level in self.fibonacci_levels}
        
        # Calculate the gain from entry to high
        gain = position_high - entry_price
        
        # Calculate retracement prices
        retracements = {}
        for level in self.fibonacci_levels:
            retracement_amount = gain * level
            retracement_price = position_high - retracement_amount
            retracements[f"{int(level*100)}%"] = round(retracement_price, 6)
        
        return retracements
    
    def get_hedge_trigger_price(self, entry_price: float, position_high: float) -> float:
        """Get the 23% retracement price that triggers hedging."""
        retracements = self.calculate_retracements(entry_price, position_high)
        return retracements["23%"]
    
    def calculate_unrealized_pnl_percent(self, entry_price: float, current_price: float) -> float:
        """Calculate unrealized P&L as percentage of entry price."""
        if entry_price <= 0:
            return 0.0
        
        return ((current_price - entry_price) / entry_price) * 100
    
    def is_new_high(self, current_price: float, previous_high: float) -> bool:
        """Check if current price is a new high for the position."""
        return current_price > previous_high


# Global calculator instance
fibonacci_calculator = FibonacciCalculator()
