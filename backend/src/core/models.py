"""
Data models for HyperTrader
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict
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
    Tracks unit changes based on FIXED price boundaries.
    CORRECTED: Uses fixed unit boundaries, not continuous calculation.
    """
    
    def __init__(self, 
                 entry_price: Optional[Decimal] = None, 
                 unit_size_usd: Decimal = Decimal("5.00")):
        """
        Initialize unit tracker with FIXED boundaries.
        
        Args:
            entry_price: Initial entry price (set on first price if None)
            unit_size_usd: Price movement that constitutes one unit (in USD)
        """
        self.entry_price = entry_price
        self.unit_size_usd = unit_size_usd
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        self.phase = Phase.ADVANCE
        
        # Fragment tracking as dicts with usd and coin_value keys
        self.position_fragment = {"usd": Decimal("0"), "coin_value": Decimal("0")}
        self.hedge_fragment = {"usd": Decimal("0"), "coin_value": Decimal("0")}
        
        # FIXED BOUNDARY TRACKING: Store actual prices at each unit level
        self.unit_boundaries: Dict[int, Decimal] = {}  # {unit: exact_price_when_reached}
        
    def _calculate_unit_price(self, unit: int) -> Decimal:
        """Calculate the exact price for a given unit level"""
        if self.entry_price is None:
            return Decimal("0")
        return self.entry_price + (Decimal(unit) * self.unit_size_usd)
    
    def calculate_unit_change(self, current_price: Decimal) -> bool:
        """
        CORRECTED: Check if price has crossed a FIXED unit boundary.
        
        Entry: $4500, Unit: $5
        - Unit 0: $4500 (entry)
        - Unit +1: Trigger when price >= $4505, stay until price <= $4495  
        - Unit -1: Trigger when price <= $4495, stay until price >= $4505
        
        Args:
            current_price: Current market price
            
        Returns:
            True if unit boundary was crossed, False otherwise
        """
        if self.entry_price is None:
            self.entry_price = current_price
            self.unit_boundaries[0] = current_price
            logger.info(f"📍 Entry price set: ${self.entry_price:.2f}")
            logger.info(f"Unit boundaries: +1 at ${self._calculate_unit_price(1):.2f}, -1 at ${self._calculate_unit_price(-1):.2f}")
            return False
        
        old_unit = self.current_unit
        new_unit = self.current_unit  # Start with current
        
        # Check if we need to move UP (positive units)
        while True:
            next_up_unit = new_unit + 1
            next_up_price = self._calculate_unit_price(next_up_unit)
            
            if current_price >= next_up_price:
                new_unit = next_up_unit
                if next_up_unit not in self.unit_boundaries:
                    self.unit_boundaries[next_up_unit] = next_up_price
                    logger.info(f"📈 UNIT BOUNDARY CROSSED: +{next_up_unit} at ${next_up_price:.2f}")
            else:
                break
        
        # Check if we need to move DOWN (negative units) 
        while True:
            next_down_unit = new_unit - 1  
            next_down_price = self._calculate_unit_price(next_down_unit)
            
            if current_price <= next_down_price:
                new_unit = next_down_unit
                if next_down_unit not in self.unit_boundaries:
                    self.unit_boundaries[next_down_unit] = next_down_price
                    logger.info(f"📉 UNIT BOUNDARY CROSSED: {next_down_unit} at ${next_down_price:.2f}")
            else:
                break
        
        # Update unit if it changed
        if new_unit != old_unit:
            self.current_unit = new_unit
            
            # Update peak tracking
            if self.current_unit > self.peak_unit:
                self.peak_unit = self.current_unit
                logger.warning(f"🎯 NEW PEAK REACHED: Unit {self.peak_unit} at ${current_price:.2f}")
            
            # Update valley tracking (only in DECLINE phase)
            if self.phase == Phase.DECLINE and self.current_unit < self.valley_unit:
                self.valley_unit = self.current_unit
                logger.warning(f"📉 NEW VALLEY REACHED: Unit {self.valley_unit} at ${current_price:.2f}")
                
            # CRITICAL: Log the unit change prominently
            direction = "🔺 UP" if new_unit > old_unit else "🔻 DOWN"
            logger.warning(f"🚨 UNIT BOUNDARY CROSSED! {direction}")
            logger.warning(f"   Unit: {old_unit} → {self.current_unit}")
            logger.warning(f"   Price: ${current_price:.2f}")
            logger.warning(f"   Phase: {self.phase.value}")
            
            # Show next boundaries
            next_up = self._calculate_unit_price(self.current_unit + 1)
            next_down = self._calculate_unit_price(self.current_unit - 1)
            logger.warning(f"   Next boundaries: +1 at ${next_up:.2f}, -1 at ${next_down:.2f}")
            
            return True
            
        return False
            
        return False
    
    def get_units_from_peak(self) -> int:
        """Get the number of units from peak (for RETRACEMENT phase)"""
        return self.current_unit - self.peak_unit
    
    def get_units_from_valley(self) -> int:
        """Get the number of units from valley (for RECOVERY phase)"""
        return self.current_unit - self.valley_unit
        
    def get_current_unit_boundaries(self) -> Dict[str, Decimal]:
        """Get the current unit's price boundaries for monitoring"""
        if self.entry_price is None:
            return {"current": Decimal("0"), "next_up": Decimal("0"), "next_down": Decimal("0")}
            
        return {
            "current": self.unit_boundaries.get(self.current_unit, self._calculate_unit_price(self.current_unit)),
            "next_up": self._calculate_unit_price(self.current_unit + 1),
            "next_down": self._calculate_unit_price(self.current_unit - 1)
        }
