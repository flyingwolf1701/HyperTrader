"""
UnitTracker Implementation - Clean boundary detection using position map
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict
from enum import Enum
from loguru import logger
from dataclasses import dataclass
from position_map import add_unit_level


class Phase(Enum):
    """Trading strategy phases"""
    ADVANCE = "ADVANCE"
    RETRACEMENT = "RETRACEMENT"
    DECLINE = "DECLINE"
    RECOVERY = "RECOVERY"


@dataclass
class UnitChangeEvent:
    """Event triggered when unit boundary is crossed"""
    old_unit: int
    new_unit: int
    price: Decimal
    direction: str  # "UP" or "DOWN"
    phase: Phase
    units_from_peak: int
    units_from_valley: int
    timestamp: datetime


class UnitTracker:
    """
    Tracks unit changes using position map for boundary detection.
    Clean boundary detection - no mathematical calculation needed.
    """
    
    def __init__(self, 
                 position_state,  # PositionState instance
                 position_map: Dict[int, any],  # Dict[unit -> PositionConfig]
                 phase: Phase = Phase.ADVANCE):
        """
        Initialize unit tracker with existing position map.
        
        Args:
            position_state: PositionState instance with entry_price, unit_size, etc.
            position_map: Dictionary mapping unit -> PositionConfig
            phase: Current strategy phase
        """
        self.position_state = position_state
        self.position_map = position_map
        self.phase = phase
        
        # Unit tracking state
        self.current_unit = 0  # Start at entry (Unit 0)
        self.peak_unit = 0
        self.valley_unit = 0
        
        # Ensure Unit 0 exists in position map
        if 0 not in self.position_map:
            logger.error("Position map must contain Unit 0 (entry level)")
            raise ValueError("Unit 0 missing from position map")
        
        logger.info(f"📍 UnitTracker initialized at Unit {self.current_unit}")
        self._log_current_boundaries()
    
    def calculate_unit_change(self, current_price: Decimal) -> Optional[UnitChangeEvent]:
        """
        Check if price has crossed a unit boundary using position map lookup.
        
        Args:
            current_price: Current market price
            
        Returns:
            UnitChangeEvent if boundary crossed, None otherwise
        """
        old_unit = self.current_unit
        new_unit = self.current_unit
        
        # Ensure we have enough units ahead in the direction we might move
        self._ensure_sufficient_units()
        
        # Check if we need to move UP to next unit
        next_unit_up = self.current_unit + 1
        if next_unit_up in self.position_map:
            price_threshold_up = self.position_map[next_unit_up].price
            
            if current_price >= price_threshold_up:
                new_unit = next_unit_up
                logger.info(f"📈 Price ${current_price} crossed UP threshold ${price_threshold_up}")
        
        # Check if we need to move DOWN to previous unit
        next_unit_down = self.current_unit - 1
        if next_unit_down in self.position_map:
            price_threshold_down = self.position_map[next_unit_down].price
            
            if current_price <= price_threshold_down:
                new_unit = next_unit_down
                logger.info(f"📉 Price ${current_price} crossed DOWN threshold ${price_threshold_down}")
        
        # Check if unit actually changed
        if new_unit == old_unit:
            return None  # No boundary crossed
        
        # Unit boundary was crossed!
        self.current_unit = new_unit
        direction = "UP" if new_unit > old_unit else "DOWN"
        
        # Check if we need to move UP to next unit
        next_unit_up = self.current_unit + 1
        if next_unit_up in self.position_map:
            price_threshold_up = self.position_map[next_unit_up].price
            
            if current_price >= price_threshold_up:
                new_unit = next_unit_up
                logger.info(f"📈 Price ${current_price} crossed UP threshold ${price_threshold_up}")
        else:
            # Need to extend position map upward
            logger.warning(f"Unit {next_unit_up} missing from position map - extending")
            self._extend_position_map_up(next_unit_up)
            return self.calculate_unit_change(current_price)  # Retry after extension
        
        # Check if we need to move DOWN to previous unit
        next_unit_down = self.current_unit - 1
        if next_unit_down in self.position_map:
            price_threshold_down = self.position_map[next_unit_down].price
            
            if current_price <= price_threshold_down:
                new_unit = next_unit_down
                logger.info(f"📉 Price ${current_price} crossed DOWN threshold ${price_threshold_down}")
        else:
            # Need to extend position map downward
            logger.warning(f"Unit {next_unit_down} missing from position map - extending")
            self._extend_position_map_down(next_unit_down)
            return self.calculate_unit_change(current_price)  # Retry after extension
        
        # Check if unit actually changed
        if new_unit == old_unit:
            return None  # No boundary crossed
        
        # Unit boundary was crossed!
        self.current_unit = new_unit
        direction = "UP" if new_unit > old_unit else "DOWN"
        
        # Update peak/valley tracking
        self._update_peak_valley_tracking()
        
        # Create and log unit change event
        event = UnitChangeEvent(
            old_unit=old_unit,
            new_unit=new_unit,
            price=current_price,
            direction=direction,
            phase=self.phase,
            units_from_peak=self.get_units_from_peak(),
            units_from_valley=self.get_units_from_valley(),
            timestamp=datetime.now()
        )
        
        # Prominent logging
        logger.warning(f"🚨 UNIT BOUNDARY CROSSED! {direction}")
        logger.warning(f"   Unit: {old_unit} → {new_unit}")
        logger.warning(f"   Price: ${current_price:.2f}")
        logger.warning(f"   Phase: {self.phase.value}")
        logger.warning(f"   From Peak: {event.units_from_peak} | From Valley: {event.units_from_valley}")
        
        self._log_current_boundaries()
        
        return event
    
    def _update_peak_valley_tracking(self):
        """Update peak and valley based on current unit and phase"""
        # Update peak (always track new highs)
        if self.current_unit > self.peak_unit:
            old_peak = self.peak_unit
            self.peak_unit = self.current_unit
            logger.warning(f"🎯 NEW PEAK REACHED: Unit {old_peak} → {self.peak_unit}")
        
        # Update valley (only during DECLINE phase)
        if self.phase == Phase.DECLINE and self.current_unit < self.valley_unit:
            old_valley = self.valley_unit
            self.valley_unit = self.current_unit
            logger.warning(f"📉 NEW VALLEY REACHED: Unit {old_valley} → {self.valley_unit}")
    
    def _ensure_sufficient_units(self):
        """
        Ensure we have the 4th unit ahead in the direction we might move.
        Only extends during ADVANCE (upward) or DECLINE (downward) phases.
        """
        
        if self.phase == Phase.ADVANCE:
            # In ADVANCE, check if we have 4 units ahead (upward)
            target_unit = self.current_unit + 4
            if target_unit not in self.position_map:
                success = add_unit_level(self.position_state, self.position_map, target_unit)
                if success:
                    logger.debug(f"➕ Added Unit {target_unit} for ADVANCE phase")
        
        elif self.phase == Phase.DECLINE:
            # In DECLINE, check if we have 4 units ahead (downward)
            target_unit = self.current_unit - 4
            if target_unit not in self.position_map:
                success = add_unit_level(self.position_state, self.position_map, target_unit)
                if success:
                    logger.debug(f"➕ Added Unit {target_unit} for DECLINE phase")
    

    
    def _log_current_boundaries(self):
        """Log current unit and its price boundaries"""
        current_price = self.position_map[self.current_unit].price
        
        # Get adjacent boundaries
        up_boundary = "N/A"
        down_boundary = "N/A"
        
        if (self.current_unit + 1) in self.position_map:
            up_boundary = f"${self.position_map[self.current_unit + 1].price:.2f}"
        
        if (self.current_unit - 1) in self.position_map:
            down_boundary = f"${self.position_map[self.current_unit - 1].price:.2f}"
        
        logger.info(f"📍 Current: Unit {self.current_unit} @ ${current_price:.2f}")
        logger.info(f"   Next boundaries: UP {up_boundary} | DOWN {down_boundary}")
    
    def get_units_from_peak(self) -> int:
        """Get the number of units from peak (for RETRACEMENT phase)"""
        return self.current_unit - self.peak_unit
    
    def get_units_from_valley(self) -> int:
        """Get the number of units from valley (for RECOVERY phase)"""
        return self.current_unit - self.valley_unit
    
    def set_phase(self, new_phase: Phase):
        """Update the current strategy phase"""
        if new_phase != self.phase:
            logger.info(f"🔄 Phase transition: {self.phase.value} → {new_phase.value}")
            self.phase = new_phase
    
    def reset_for_new_cycle(self, new_entry_price: Optional[Decimal] = None):
        """
        Reset unit tracking for a new strategy cycle.
        
        Args:
            new_entry_price: Optional new entry price for the cycle
        """
        logger.warning("🔄 RESET: Starting new strategy cycle")
        
        # Reset unit tracking
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        self.phase = Phase.ADVANCE
        
        # Update entry price if provided
        if new_entry_price:
            self.position_state.entry_price = new_entry_price
            logger.info(f"📍 New entry price: ${new_entry_price:.2f}")
        
        # Log reset completion
        logger.warning("✅ Reset complete - ready for new cycle")
        self._log_current_boundaries()
    
    def get_status_summary(self) -> Dict:
        """Get current unit tracker status for debugging/monitoring"""
        return {
            "current_unit": self.current_unit,
            "peak_unit": self.peak_unit,
            "valley_unit": self.valley_unit,
            "phase": self.phase.value,
            "units_from_peak": self.get_units_from_peak(),
            "units_from_valley": self.get_units_from_valley(),
            "entry_price": float(self.position_state.entry_price),
            "unit_size": float(self.position_state.unit_size_usd)
        }


# Usage example for integration
if __name__ == "__main__":
    # Example of how this would be used with existing systems
    
    # Assuming you have position_state and position_map from existing code
    # position_state = PositionState(...)
    # position_map = calculate_initial_position_map(...)
    
    # Initialize unit tracker
    # unit_tracker = UnitTracker(position_state, position_map)
    
    # In WebSocket price handler:
    # async def handle_price_update(price: Decimal):
    #     event = unit_tracker.calculate_unit_change(price)
    #     
    #     if event:
    #         logger.warning(f"Unit change: {event.old_unit} → {event.new_unit}")
    #         
    #         # Trigger strategy actions based on event
    #         await strategy.handle_unit_change(event)
    
    pass