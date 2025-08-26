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
    Stage 1 & 2 implementation.
    """
    
    def __init__(self, 
                 entry_price: Optional[Decimal] = None, 
                 unit_size: Decimal = Decimal("2.0")):
        """
        Initialize unit tracker.
        
        Args:
            entry_price: Initial entry price (set on first price if None)
            unit_size: Price movement that constitutes one unit
        """
        self.entry_price = entry_price
        self.unit_size = unit_size
        self.current_unit = 0
        self.peak_unit = 0  # Stage 2
        self.valley_unit = 0  # Stage 2
        self.phase = Phase.ADVANCE  # Stage 2
        self.position_fragment = Decimal("0")  # Stage 2
        self.hedge_fragment = Decimal("0")  # Stage 2
        
        # Debouncing to prevent rapid oscillation
        self.last_stable_unit = 0
        self.pending_unit = None
        self.pending_unit_time = None
        self.debounce_seconds = 3  # Wait 3 seconds before confirming unit change
        
    def calculate_unit_change(self, current_price: Decimal) -> bool:
        """
        Calculate if a unit change has occurred with debouncing.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if unit changed and stabilized, False otherwise
        """
        if self.entry_price is None:
            self.entry_price = current_price
            logger.info(f"Entry price set to: ${self.entry_price:.2f}")
            return False
            
        # Calculate how many units away from entry price
        price_delta = current_price - self.entry_price
        new_unit = int(price_delta / self.unit_size)
        
        current_time = datetime.now()
        
        # Check if this is a new unit level
        if new_unit != self.last_stable_unit:
            # Skip debouncing if debounce_seconds is 0
            if self.debounce_seconds <= 0:
                # Immediate confirmation
                old_unit = self.current_unit
                self.current_unit = new_unit
                self.last_stable_unit = new_unit
                
                # Update peak (always track the highest unit reached)
                if self.current_unit > self.peak_unit:
                    self.peak_unit = self.current_unit
                
                # Update valley only in DECLINE phase (per strategy doc)
                if self.phase == Phase.DECLINE and self.current_unit < self.valley_unit:
                    self.valley_unit = self.current_unit
                    
                logger.info(f"*** UNIT CHANGE: {old_unit} -> {self.current_unit} ***")
                return True
            
            # If this is a different unit than pending, update pending
            if new_unit != self.pending_unit:
                self.pending_unit = new_unit
                self.pending_unit_time = current_time
                logger.debug(f"Pending unit change: {self.last_stable_unit} -> {new_unit}")
                return False
            
            # Check if pending unit has stabilized
            if self.pending_unit_time and (current_time - self.pending_unit_time) >= timedelta(seconds=self.debounce_seconds):
                # Unit has stabilized, confirm the change
                old_unit = self.current_unit
                self.current_unit = new_unit
                self.last_stable_unit = new_unit
                self.pending_unit = None
                self.pending_unit_time = None
                
                # Update peak (always track the highest unit reached)
                if self.current_unit > self.peak_unit:
                    self.peak_unit = self.current_unit
                
                # Update valley only in DECLINE phase (per strategy doc)
                # Valley tracks lowest unit reached during DECLINE phase
                if self.phase == Phase.DECLINE and self.current_unit < self.valley_unit:
                    self.valley_unit = self.current_unit
                    
                logger.info(f"*** CONFIRMED UNIT CHANGE: {old_unit} -> {self.current_unit} ***")
                return True
        else:
            # Price returned to stable unit, clear pending
            self.pending_unit = None
            self.pending_unit_time = None
            
        return False
    
    def get_units_from_peak(self) -> int:
        """Get the number of units from peak (for RETRACEMENT phase)"""
        return self.current_unit - self.peak_unit
    
    def get_units_from_valley(self) -> int:
        """Get the number of units from valley (for RECOVERY phase)"""
        return self.current_unit - self.valley_unit