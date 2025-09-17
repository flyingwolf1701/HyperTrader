"""
UnitTracker Implementation - Clean sliding window strategy
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger

# Import from centralized data models
from .data_models import Phase, UnitChangeEvent


class UnitTracker:
    """
    Tracks unit changes and manages sliding window order system.
    Implements v9.2.6 sliding window strategy.
    """
    
    def __init__(self,
                 position_state,
                 position_map: Dict[int, any]):
        """
        Initialize unit tracker with sliding window management.
        As per data_flow.md - simple list-based tracking.

        Args:
            position_state: Static position configuration
            position_map: Dynamic unit-based order tracking
        """
        self.position_state = position_state
        self.position_map = position_map
        self.current_unit = 0
        self.last_phase = "advance"  # Track last phase for recovery detection

        # Sliding window management - SIMPLE LIST-BASED TRACKING from data_flow.md
        self.trailing_stop: List[int] = [-4, -3, -2, -1]  # Initial 4 stop-loss orders
        self.trailing_buy: List[int] = []   # Initially empty
        self.current_realized_pnl = Decimal(0)  # Track PnL for reinvestment

        if 0 not in self.position_map:
            raise ValueError("Unit 0 missing from position map")

        logger.info(f"UnitTracker initialized with stop-losses at {self.trailing_stop}")
    
    
    def calculate_unit_change(self, current_price: Decimal) -> Optional[UnitChangeEvent]:
        """
        Check if price has crossed a unit boundary and manage sliding window.
        Properly handles rapid price movements that skip units.
        """
        self._ensure_sufficient_units()

        previous_unit = self.current_unit

        # Calculate which unit the current price belongs to
        # Unit = floor((price - entry_price) / unit_size)
        price_diff = current_price - self.position_state.entry_price
        unit_size = self.position_state.unit_size_usd

        # Calculate the actual unit we should be in
        new_unit = int(price_diff / unit_size)
        # Handle negative rounding correctly
        if price_diff < 0 and price_diff % unit_size != 0:
            new_unit -= 1

        # Ensure the unit exists in position map
        if new_unit not in self.position_map:
            from .position_map import add_unit_level
            add_unit_level(self.position_state, self.position_map, new_unit)

        # Update current unit if it changed
        if new_unit != previous_unit:
            self.current_unit = new_unit
            direction = 'up' if new_unit > previous_unit else 'down'

            # Log if we skipped units (rapid price movement)
            units_skipped = abs(new_unit - previous_unit) - 1
            if units_skipped > 0:
                logger.warning(f"Rapid price movement detected! Skipped {units_skipped} units: {previous_unit} → {new_unit}")

            # Update trailing lists to reflect new position
            self._update_trailing_lists_for_movement(previous_unit, new_unit)
        else:
            return None

        # If unit changed, create event
        if self.current_unit != previous_unit:
            current_phase = self.get_phase()

            # Create window composition string
            window_comp = f"{len(self.trailing_stop)}S/{len(self.trailing_buy)}B"

            return UnitChangeEvent(
                price=current_price,
                phase=Phase.ADVANCE if current_phase == "advance" else
                      Phase.DECLINE if current_phase == "decline" else
                      Phase.RETRACEMENT if current_phase == "retracement" else
                      Phase.RECOVER,
                current_unit=self.current_unit,
                timestamp=datetime.now(),
                direction=direction,
                window_composition=window_comp
            )

        return None
    
    
    def get_phase(self) -> str:
        """
        Simple phase detection based on list lengths as per data_flow.md.
        Phase names are mostly for documentation and logging.
        """
        stop_count = len(self.trailing_stop)
        buy_count = len(self.trailing_buy)

        # Determine the current phase
        match (stop_count, buy_count):
            case (4, 0):
                # Pure long position with stops
                current_phase = "advance"

            case (0, 4):
                # Pure cash position with buy orders
                current_phase = "decline"

            case (s, b) if s > 0 and b > 0:
                # Mixed state - have both stops and buys
                # Retracement if we were in advance, recovery if we were in decline
                if self.last_phase in ["advance", "retracement"]:
                    current_phase = "retracement"
                else:
                    current_phase = "recovery"

            case _:
                # Edge case - shouldn't normally happen
                current_phase = self.last_phase if hasattr(self, 'last_phase') else "advance"

        # Update last_phase for next call
        self.last_phase = current_phase
        return current_phase
    
    
    def _ensure_sufficient_units(self):
        """
        Ensure we have units for the sliding window (4 ahead and 4 behind).
        """
        from .position_map import add_unit_level

        # Ensure we have 5 units ahead and behind for window management
        for offset in range(-5, 6):
            target_unit = self.current_unit + offset
            if target_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, target_unit)

    def _update_trailing_lists_for_movement(self, previous_unit: int, new_unit: int):
        """
        Update trailing stop and buy lists when unit changes.
        Maintains the 4-order constraint and keeps orders relative to current position.
        """
        # Remove any stops that are now above current unit
        stops_to_remove = [u for u in self.trailing_stop if u > new_unit]
        for stop in stops_to_remove:
            self.trailing_stop.remove(stop)
            logger.debug(f"Removed stop at unit {stop} (now above current unit {new_unit})")

        # Remove any buys that are now below current unit
        buys_to_remove = [u for u in self.trailing_buy if u < new_unit]
        for buy in buys_to_remove:
            self.trailing_buy.remove(buy)
            logger.debug(f"Removed buy at unit {buy} (now below current unit {new_unit})")

        # Keep lists sorted
        self.trailing_stop.sort()
        self.trailing_buy.sort()
    
    
    def get_window_state(self) -> Dict:
        """
        Get current sliding window state for monitoring.
        """
        return {
            'current_unit': self.current_unit,
            'phase': self.get_phase(),
            'trailing_stop': self.trailing_stop.copy(),
            'trailing_buy': self.trailing_buy.copy(),
            'total_orders': len(self.trailing_stop) + len(self.trailing_buy),
            'current_realized_pnl': float(self.current_realized_pnl)
        }
    # NEW LIST-BASED TRACKING METHODS
    def add_trailing_stop(self, unit: int) -> bool:
        """Add a unit to trailing stop list if not already present"""
        if unit not in self.trailing_stop:
            self.trailing_stop.append(unit)
            self.trailing_stop.sort()  # Keep sorted for readability
            logger.debug(f"Added stop at unit {unit}, trailing_stop: {self.trailing_stop}")
            return True
        return False
    
    def remove_trailing_stop(self, unit: int) -> bool:
        """Remove a unit from trailing stop list"""
        if unit in self.trailing_stop:
            self.trailing_stop.remove(unit)
            logger.debug(f"Removed stop at unit {unit}, trailing_stop: {self.trailing_stop}")
            return True
        return False
    
    def add_trailing_buy(self, unit: int) -> bool:
        """Add a unit to trailing buy list if not already present"""
        if unit not in self.trailing_buy:
            self.trailing_buy.append(unit)
            self.trailing_buy.sort()  # Keep sorted for readability
            logger.debug(f"Added buy at unit {unit}, trailing_buy: {self.trailing_buy}")
            return True
        return False
    
    def remove_trailing_buy(self, unit: int) -> bool:
        """Remove a unit from trailing buy list"""
        if unit in self.trailing_buy:
            self.trailing_buy.remove(unit)
            logger.debug(f"Removed buy at unit {unit}, trailing_buy: {self.trailing_buy}")
            return True
        return False

    def track_realized_pnl(self, sell_price: Decimal, buy_price: Decimal, size: Decimal):
        """Track realized PnL from a completed buy-sell cycle

        Args:
            sell_price: Price at which we sold
            buy_price: Price at which we bought (or entry price)
            size: Size of the transaction in asset terms
        """
        pnl = (sell_price - buy_price) * size
        self.current_realized_pnl += pnl
        logger.info(f"Realized PnL: ${pnl:.2f} (Total: ${self.current_realized_pnl:.2f})")

    def get_adjusted_fragment_usd(self) -> Decimal:
        """Get fragment size adjusted for realized PnL (for recovery phase)

        In recovery phase, we reinvest PnL by dividing it by 4 and adding to fragments
        """
        if self.get_phase() == "recovery" and self.current_realized_pnl > 0:
            pnl_per_fragment = self.current_realized_pnl / Decimal("4")
            adjusted_fragment = self.position_state.long_fragment_usd + pnl_per_fragment
            logger.debug(f"Adjusted fragment: ${adjusted_fragment:.2f} (base: ${self.position_state.long_fragment_usd:.2f} + pnl: ${pnl_per_fragment:.2f})")
            return adjusted_fragment
        return self.position_state.long_fragment_usd