"""
Unit Tracker: Pure price interpreter that translates price feed to unit movements.
Emits UnitChangeEvent whenever the price crosses a unit boundary.
"""

from decimal import Decimal
from dataclasses import dataclass
from typing import Optional, Callable
from loguru import logger
from enum import Enum


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass
class UnitChangeEvent:
    """Event emitted when price crosses a unit boundary"""
    previous_unit: int
    current_unit: int
    price: Decimal
    previous_direction: Direction
    current_direction: Direction
    is_whipsaw: bool = False
# TODO: seems we are using is_whipsaw and is_pause for the same thing. But there might be reason to it. But need to understand better

class UnitTracker:
    """
    Pure price interpreter that tracks unit movements.
    Has no knowledge of orders or positions.
    """

    def __init__(self, unit_size_usd: Decimal, anchor_price: Decimal):
        """
        Initialize the unit tracker.

        Args:
            unit_size_usd: Fixed dollar amount that defines one unit (e.g., $100 for BTC)
            anchor_price: The anchor price at unit 0 (initial position entry price)
        """
        self.unit_size_usd = unit_size_usd

        # Anchor is always at unit 0
        self.anchor_price = anchor_price
        self.current_unit = 0
        self.previous_unit = 0

        # Direction tracking
        self.current_direction = Direction.NONE
        self.previous_direction = Direction.UP

        # Whipsaw detection
        self.whipsaw_pattern = []  # Track last 3 unit movements
        self.is_paused = False

        # Event callback
        self.on_unit_change: Optional[Callable[[UnitChangeEvent], None]] = None

        # Price tracking - will be updated via WebSocket
        self.current_price = anchor_price

        logger.info(f"UnitTracker initialized - Anchor: ${anchor_price:.2f} at unit 0, Unit Size: ${unit_size_usd}")

    def update_price(self, price: Decimal) -> Optional[UnitChangeEvent]:
        """
        Update the current price and check for unit boundary crossings.

        Args:
            price: New market price

        Returns:
            UnitChangeEvent if a unit boundary was crossed, None otherwise
        """
        self.current_price = price

        # Calculate the new unit based on price
        price_diff = price - self.anchor_price
        new_unit = int(price_diff / self.unit_size_usd)

        # Check if we've crossed a unit boundary
        if new_unit != self.current_unit:
            # Store previous state
            self.previous_unit = self.current_unit
            self.previous_direction = self.current_direction

            # Update current state
            self.current_unit = new_unit

            # Determine new direction
            if self.current_unit > self.previous_unit:
                self.current_direction = Direction.UP
            elif self.current_unit < self.previous_unit:
                self.current_direction = Direction.DOWN
            else:
                self.current_direction = Direction.NONE

            # Check for whipsaw pattern (A -> B -> A)
            is_whipsaw = self._check_whipsaw()

            # Create event
            event = UnitChangeEvent(
                previous_unit=self.previous_unit,
                current_unit=self.current_unit,
                price=price,
                previous_direction=self.previous_direction,
                current_direction=self.current_direction,
                is_whipsaw=is_whipsaw
            )

            # Log the unit change
            direction_symbol = "↑" if self.current_direction == Direction.UP else "↓"
            whipsaw_text = " [WHIPSAW]" if is_whipsaw else ""
            logger.info(
                f"Unit Change: {self.previous_unit} → {self.current_unit} {direction_symbol} "
                f"@ ${price:.2f}{whipsaw_text}"
            )

            # Trigger callback if registered
            if self.on_unit_change:
                self.on_unit_change(event)

            return event

        return None

    def _check_whipsaw(self) -> bool:
        """
        Check if the current movement completes a whipsaw pattern (A -> B -> A).

        Returns:
            True if whipsaw detected, False otherwise
        """
        # Update pattern history
        self.whipsaw_pattern.append(self.current_unit)
        if len(self.whipsaw_pattern) > 3:
            self.whipsaw_pattern.pop(0)

        # Check for A -> B -> A pattern
        if len(self.whipsaw_pattern) == 3:
            if self.whipsaw_pattern[0] == self.whipsaw_pattern[2] and \
               self.whipsaw_pattern[0] != self.whipsaw_pattern[1]:
                logger.warning(
                    f"Whipsaw detected: {self.whipsaw_pattern[0]} → "
                    f"{self.whipsaw_pattern[1]} → {self.whipsaw_pattern[2]}"
                )
                self.is_paused = True
                return True

        # Clear pause state if we've moved beyond the whipsaw
        if self.is_paused and len(self.whipsaw_pattern) == 3:
            # We've moved to a new unit after the whipsaw
            self.is_paused = False
            logger.info("Whipsaw resolved - resuming normal operation")

        return False

    def get_unit_price(self, unit: int) -> Decimal:
        """
        Calculate the price for a specific unit.

        Note: While the position_map stores these prices, the unit_tracker
        calculates them independently for unit boundary detection.

        Args:
            unit: Unit number (0 is anchor price)

        Returns:
            Price at the unit boundary
        """
        return self.anchor_price + (Decimal(unit) * self.unit_size_usd)

    def get_state(self) -> dict:
        """
        Get current state for logging/debugging.

        Returns:
            Dictionary containing current state
        """
        return {
            "current_unit": self.current_unit,
            "previous_unit": self.previous_unit,
            "current_direction": self.current_direction.value,
            "previous_direction": self.previous_direction.value,
            "current_price": float(self.current_price),
            "anchor_price": float(self.anchor_price),
            "unit_size_usd": float(self.unit_size_usd),
            "is_paused": self.is_paused,
            "whipsaw_pattern": self.whipsaw_pattern
        }