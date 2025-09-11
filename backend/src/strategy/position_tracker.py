"""
Position Tracker for HyperTrader Long Wallet
Tracks position state, unit movements, and compound growth
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger
from .data_models import (
    PositionState, Phase, UnitChangeEvent, 
    CompoundGrowthMetrics
)


class PositionTracker:
    """
    Tracks position state and unit movements for the long wallet strategy.
    Manages unit boundary detection and compound growth tracking.
    """
    
    def __init__(self, position_state: PositionState, unit_size_usd: Decimal):
        """
        Initialize the position tracker.
        
        Args:
            position_state: Static position configuration
            unit_size_usd: USD price movement per unit
        """
        self.position_state = position_state
        self.unit_size_usd = unit_size_usd
        
        # Unit tracking
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        
        # Price tracking
        self.last_price = position_state.entry_price
        self.current_price = position_state.entry_price
        
        # History tracking
        self.unit_history: List[UnitChangeEvent] = []
        self.max_units_traveled = 0
        
        # Growth tracking
        self.cycle_high_value = position_state.position_value_usd
        self.cycle_low_value = position_state.position_value_usd
        
        logger.info(f"Position tracker initialized at unit 0, price ${position_state.entry_price:.2f}")
    
    def check_unit_change(self, current_price: Decimal, current_phase: Phase) -> Optional[UnitChangeEvent]:
        """
        Check if price has crossed a unit boundary.
        
        Args:
            current_price: Current market price
            current_phase: Current strategy phase
            
        Returns:
            UnitChangeEvent if boundary crossed, None otherwise
        """
        self.last_price = self.current_price
        self.current_price = current_price
        
        # Calculate which unit we're in based on entry price
        price_diff = current_price - self.position_state.entry_price
        units_from_entry = price_diff / self.unit_size_usd
        new_unit = int(units_from_entry)
        
        # Check if we've crossed a boundary
        if new_unit != self.current_unit:
            old_unit = self.current_unit
            self.current_unit = new_unit
            
            # Determine direction
            direction = 'up' if new_unit > old_unit else 'down'
            
            # Update peak/valley tracking
            if new_unit > self.peak_unit:
                self.peak_unit = new_unit
                logger.debug(f"New peak unit: {self.peak_unit}")
            
            if new_unit < self.valley_unit:
                self.valley_unit = new_unit
                logger.debug(f"New valley unit: {self.valley_unit}")
            
            # Track max distance traveled
            distance_from_entry = abs(new_unit)
            if distance_from_entry > self.max_units_traveled:
                self.max_units_traveled = distance_from_entry
            
            # Create unit change event
            event = UnitChangeEvent(
                price=current_price,
                phase=current_phase,
                current_unit=new_unit,
                units_from_peak=new_unit - self.peak_unit,
                units_from_valley=new_unit - self.valley_unit,
                timestamp=datetime.now(),
                direction=direction
            )
            
            # Add to history
            self.unit_history.append(event)
            
            logger.info(f"Unit boundary crossed: {old_unit} → {new_unit} "
                       f"(price: ${current_price:.2f}, direction: {direction})")
            
            return event
        
        return None
    
    def get_unit_price(self, unit: int) -> Decimal:
        """
        Calculate the price at a specific unit level.
        
        Args:
            unit: Unit level
            
        Returns:
            Price at that unit
        """
        return self.position_state.get_price_for_unit(unit)
    
    def calculate_compound_growth(self, current_position_value: Decimal) -> Decimal:
        """
        Calculate compound growth factor from original position.
        
        Args:
            current_position_value: Current value of position
            
        Returns:
            Growth factor (1.0 = no growth, 2.0 = doubled, etc.)
        """
        if self.position_state.original_position_value_usd > 0:
            return current_position_value / self.position_state.original_position_value_usd
        return Decimal("1.0")
    
    def update_position_value(self, new_asset_size: Decimal, current_price: Decimal):
        """
        Update current position value and size.
        
        Args:
            new_asset_size: New asset amount
            current_price: Current market price
        """
        self.position_state.asset_size = new_asset_size
        self.position_state.position_value_usd = new_asset_size * current_price
        
        # Track cycle highs and lows
        if self.position_state.position_value_usd > self.cycle_high_value:
            self.cycle_high_value = self.position_state.position_value_usd
        
        if self.position_state.position_value_usd < self.cycle_low_value:
            self.cycle_low_value = self.position_state.position_value_usd
    
    def reset_for_new_cycle(self, new_position_value: Decimal, new_asset_size: Decimal):
        """
        Reset tracking for new cycle after RESET.
        
        Args:
            new_position_value: New position value after compound growth
            new_asset_size: New asset size after compound growth
        """
        # Calculate growth for this cycle
        growth_factor = self.calculate_compound_growth(new_position_value)
        
        logger.info(f"=== CYCLE {self.position_state.cycle_number} COMPLETE ===")
        logger.info(f"Growth this cycle: {growth_factor:.2%}")
        logger.info(f"Starting value: ${self.position_state.original_position_value_usd:.2f}")
        logger.info(f"Ending value: ${new_position_value:.2f}")
        
        # Update position state for new cycle
        self.position_state.update_for_reset(new_asset_size, new_position_value)
        
        # Reset unit tracking
        self.current_unit = 0
        self.peak_unit = 0
        self.valley_unit = 0
        
        # Reset cycle tracking
        self.cycle_high_value = new_position_value
        self.cycle_low_value = new_position_value
        
        # Clear history for new cycle (keep last 10 for reference)
        if len(self.unit_history) > 10:
            self.unit_history = self.unit_history[-10:]
        
        logger.info(f"=== CYCLE {self.position_state.cycle_number} STARTED ===")
        logger.info(f"Cumulative growth: {self.position_state.cumulative_growth:.2%}")
        logger.info(f"New fragments: {self.position_state.long_fragment_asset:.6f} asset, "
                   f"${self.position_state.long_fragment_usd:.2f} USD")
    
    def get_units_from_peak(self) -> int:
        """
        Get the number of units from peak (for retracement tracking).
        
        Returns:
            Units below peak (negative number)
        """
        return self.current_unit - self.peak_unit
    
    def get_units_from_valley(self) -> int:
        """
        Get the number of units from valley (for recovery tracking).
        
        Returns:
            Units above valley (positive number)
        """
        return self.current_unit - self.valley_unit
    
    def get_position_summary(self) -> Dict:
        """
        Get comprehensive position summary.
        
        Returns:
            Dictionary with position metrics
        """
        current_growth = self.calculate_compound_growth(self.position_state.position_value_usd)
        
        return {
            'current_unit': self.current_unit,
            'peak_unit': self.peak_unit,
            'valley_unit': self.valley_unit,
            'units_from_peak': self.get_units_from_peak(),
            'units_from_valley': self.get_units_from_valley(),
            'current_price': float(self.current_price),
            'entry_price': float(self.position_state.entry_price),
            'asset_size': float(self.position_state.asset_size),
            'position_value_usd': float(self.position_state.position_value_usd),
            'cycle_number': self.position_state.cycle_number,
            'current_cycle_growth': float(current_growth),
            'cumulative_growth': float(self.position_state.cumulative_growth),
            'max_units_traveled': self.max_units_traveled
        }
    
    def get_growth_metrics(self) -> CompoundGrowthMetrics:
        """
        Get detailed compound growth metrics.
        
        Returns:
            CompoundGrowthMetrics object with growth statistics
        """
        current_growth = self.calculate_compound_growth(self.position_state.position_value_usd)
        
        # Calculate average growth per cycle
        if self.position_state.cycle_number > 0:
            avg_growth = (self.position_state.cumulative_growth ** (Decimal("1") / Decimal(str(self.position_state.cycle_number))))
        else:
            avg_growth = Decimal("1.0")
        
        # For now, best/worst are current (would track across cycles in production)
        best_growth = current_growth
        worst_growth = current_growth
        
        return CompoundGrowthMetrics(
            initial_value=self.position_state.cycle_start_value,
            current_value=self.position_state.position_value_usd,
            total_cycles=self.position_state.cycle_number,
            cumulative_growth=self.position_state.cumulative_growth,
            average_growth_per_cycle=avg_growth,
            best_cycle_growth=best_growth,
            worst_cycle_growth=worst_growth,
            current_cycle_start_value=self.position_state.original_position_value_usd
        )
    
    def estimate_next_reset(self, current_phase: Phase) -> Optional[int]:
        """
        Estimate units until next RESET based on current phase.
        
        Args:
            current_phase: Current strategy phase
            
        Returns:
            Estimated units until RESET, None if uncertain
        """
        if current_phase == Phase.ADVANCE:
            # Need to retrace 4 units then recover back
            return abs(self.get_units_from_peak()) + 8  # Down 4, back up 4
        
        elif current_phase == Phase.RETRACEMENT:
            # Depends on how many orders have triggered
            return None  # Too variable to estimate
        
        elif current_phase == Phase.DECLINE:
            # Need to recover 4 units
            return 4 - self.get_units_from_valley()
        
        elif current_phase == Phase.RECOVER:
            # Almost there, just need remaining buys to fill
            return None  # Depends on order state
        
        return None
    
    def should_add_unit_to_map(self, unit: int, position_map: Dict) -> bool:
        """
        Check if a unit should be added to position map.
        
        Args:
            unit: Unit to check
            position_map: Current position map
            
        Returns:
            True if unit should be added
        """
        # Always ensure we have units within window range
        min_unit = self.current_unit - 5
        max_unit = self.current_unit + 5
        
        if min_unit <= unit <= max_unit and unit not in position_map:
            return True
        
        # Also add peak and valley units
        if unit in [self.peak_unit, self.valley_unit] and unit not in position_map:
            return True
        
        return False
    
    def get_unit_history(self, limit: int = 10) -> List[Dict]:
        """
        Get recent unit change history.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of unit change events
        """
        history = []
        for event in self.unit_history[-limit:]:
            history.append({
                'timestamp': event.timestamp.isoformat(),
                'unit': event.current_unit,
                'price': float(event.price),
                'phase': event.phase.value,
                'direction': event.direction,
                'from_peak': event.units_from_peak,
                'from_valley': event.units_from_valley
            })
        return history