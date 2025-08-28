"""
Data models for HyperTrader
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
from loguru import logger


class Phase(Enum):
    """Trading strategy phases"""
    ADVANCE = "ADVANCE"
    RETRACEMENT = "RETRACEMENT"
    DECLINE = "DECLINE"
    RECOVERY = "RECOVERY"


class UnitTracker:
    """
    Tracks unit changes based on price movements.
    Simplified implementation without debouncing.
    """
    
    def __init__(self, 
                 entry_price: Optional[Decimal] = None, 
                 unit_value: Decimal = Decimal("2.0")):
        """
        Initialize unit tracker.
        
        Args:
            entry_price: Initial entry price (set on first price if None)
            unit_value: Price movement that constitutes one unit (in USD)
        """
        self.entry_price = entry_price
        self.unit_value = unit_value
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        self.phase = Phase.ADVANCE
        
        # Fragment tracking as dicts with usd and coin_value keys
        self.position_fragment = {"usd": Decimal("0"), "coin_value": Decimal("0")}
        self.hedge_fragment = {"usd": Decimal("0"), "coin_value": Decimal("0")}
        
        # Price tracking using dicts with unit as key
        self.peak_unit_prices = {}  # {0: entry_price, 1: price_at_unit_1, ...}
        self.valley_unit_prices = {}  # {0: entry_price, -1: price_at_unit_-1, ...}
        
    def calculate_unit_change(self, current_price: Decimal) -> bool:
        """
        Calculate if a unit change has occurred - SIMPLIFIED VERSION.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if unit changed, False otherwise
        """
        if self.entry_price is None:
            self.entry_price = current_price
            self.peak_unit_prices[0] = current_price
            self.valley_unit_prices[0] = current_price
            logger.info(f"📍 Entry price set: ${self.entry_price:.2f}")
            return False
            
        # Direct calculation - no debouncing
        price_delta = current_price - self.entry_price
        new_unit = int(price_delta / self.unit_value)
        
        # Check if unit has changed
        if new_unit != self.current_unit:
            old_unit = self.current_unit
            self.current_unit = new_unit
            
            # Update peak tracking
            if self.current_unit > self.peak_unit:
                self.peak_unit = self.current_unit
                self.peak_unit_prices[self.peak_unit] = current_price
                logger.info(f"📈 NEW PEAK: Unit {self.peak_unit} at ${current_price:.2f}")
            
            # Update valley tracking (only in DECLINE phase)
            if self.phase == Phase.DECLINE and self.current_unit < self.valley_unit:
                self.valley_unit = self.current_unit
                self.valley_unit_prices[self.valley_unit] = current_price
                logger.info(f"📉 NEW VALLEY: Unit {self.valley_unit} at ${current_price:.2f}")
                
            logger.success(f"⚡ UNIT CHANGED: {old_unit} → {self.current_unit}")
            return True
            
        return False
    
    def get_units_from_peak(self) -> int:
        """Get the number of units from peak (for RETRACEMENT phase)"""
        return self.current_unit - self.peak_unit
    
    def get_units_from_valley(self) -> int:
        """Get the number of units from valley (for RECOVERY phase)"""
        return self.current_unit - self.valley_unit