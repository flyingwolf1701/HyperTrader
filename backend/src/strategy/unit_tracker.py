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
        Initialize unit tracker with sliding window management (v10).
        Simple list-based tracking for 4-order window.

        Args:
            position_state: Static position configuration
            position_map: Dynamic unit-based order tracking
        """
        self.position_state = position_state
        self.position_map = position_map
        self.current_unit = 0

        # Sliding window management - v10 simplified tracking
        # Start empty - will be populated as orders are actually placed
        self.trailing_stop: List[int] = []  # Will hold stop-loss order units
        self.trailing_buy: List[int] = []   # Will hold buy order units
        self.current_realized_pnl = Decimal(0)  # Track PnL for organic compounding

        if 0 not in self.position_map:
            raise ValueError("Unit 0 missing from position map")

        logger.info(f"UnitTracker initialized (empty, will populate as orders are placed)")
    
    
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

            # Map phase names to enum values
            phase_enum = Phase.FULL_POSITION if current_phase == "full_position" else \
                        Phase.FULL_CASH if current_phase == "full_cash" else \
                        Phase.MIXED

            return UnitChangeEvent(
                price=current_price,
                phase=phase_enum,
                current_unit=self.current_unit,
                timestamp=datetime.now(),
                direction=direction,
                window_composition=window_comp
            )

        return None
    
    
    def get_phase(self) -> str:
        """
        Simple phase detection for v10 - based purely on order composition.
        Returns descriptive phase name for logging.
        """
        stop_count = len(self.trailing_stop)
        buy_count = len(self.trailing_buy)

        # Determine the current phase
        if stop_count == 4 and buy_count == 0:
            return "full_position"  # 100% position, 4 sells
        elif stop_count == 0 and buy_count == 4:
            return "full_cash"      # 100% cash, 4 buys
        elif stop_count + buy_count == 4:
            return "mixed"          # Mix of sells and buys
        else:
            # This shouldn't happen in normal operation
            logger.warning(f"Unexpected order composition: {stop_count} stops, {buy_count} buys")
            return "unknown"
    
    
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
        """Get fragment size adjusted for realized PnL (v10 organic compounding)

        When placing buy orders, add accumulated PnL divided by number of active buys.
        This provides organic compounding without explicit reset phases.
        """
        buy_count = len(self.trailing_buy)

        # Base fragment is 25% of original position
        base_fragment = self.position_state.long_fragment_usd

        # If we have buy orders and realized PnL, add the PnL
        if buy_count > 0 and self.current_realized_pnl > 0:
            # Divide PnL by number of active buy orders
            pnl_per_buy = self.current_realized_pnl / Decimal(str(buy_count))
            adjusted_fragment = base_fragment + pnl_per_buy
            logger.debug(f"Adjusted buy fragment: ${adjusted_fragment:.2f} (base: ${base_fragment:.2f} + pnl: ${pnl_per_buy:.2f})")
            return adjusted_fragment

        return base_fragment