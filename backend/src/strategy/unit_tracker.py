"""
Unit Tracker: Pure price interpreter that translates price feed to unit movements.
Emits UnitChangeEvent whenever the price crosses a unit boundary.
"""

import math
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

        # Direction tracking - start as UP since we're long-biased
        self.current_direction = Direction.UP
        self.previous_direction = Direction.UP

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
        new_unit = math.floor(price_diff / self.unit_size_usd)

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

            # Create event
            event = UnitChangeEvent(
                previous_unit=self.previous_unit,
                current_unit=self.current_unit,
                price=price,
                previous_direction=self.previous_direction,
                current_direction=self.current_direction
            )

            # Log unit change
            logger.info(f"🔄 UNIT CHANGE: {self.previous_unit} → {self.current_unit} (price: ${price:.2f})")

            # Trigger callback if registered
            if self.on_unit_change:
                self.on_unit_change(event)

            return event

        return None

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
            "unit_size_usd": float(self.unit_size_usd)
        }