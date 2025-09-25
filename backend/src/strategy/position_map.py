"""
Position Map: Primary historical ledger for the system.
Tracks all orders placed at each unit level with complete history.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class OrderRecord:
    """Record of a single order at a unit level"""
    order_id: str
    order_type: str  # "buy" or "sell"
    status: str  # "active", "filled", "cancelled"
    size: Decimal
    price: Decimal
    timestamp: datetime
    fill_price: Optional[Decimal] = None
    fill_timestamp: Optional[datetime] = None


@dataclass
class UnitLevel:
    """All information for a specific unit level"""
    unit: int
    price: Decimal
    orders: List[OrderRecord] = field(default_factory=list)

    def add_order(self, order_id: str, order_type: str, size: Decimal) -> None:
        """Add a new order to this unit level"""
        self.orders.append(OrderRecord(
            order_id=order_id,
            order_type=order_type,
            status="active",
            size=size,
            price=self.price,
            timestamp=datetime.now()
        ))

    def update_order_status(self, order_id: str, status: str, fill_price: Optional[Decimal] = None) -> bool:
        """Update the status of an order"""
        for order in self.orders:
            if order.order_id == order_id:
                order.status = status
                if status == "filled" and fill_price:
                    order.fill_price = fill_price
                    order.fill_timestamp = datetime.now()
                return True
        return False

    def get_active_orders(self) -> List[OrderRecord]:
        """Get all active orders at this level"""
        return [o for o in self.orders if o.status == "active"]


class PositionMap:
    """
    Primary historical ledger for the system.
    Dictionary where each key is a unit and value contains price and order history.
    """

    def __init__(self, initial_unit: int = 0, unit_size: Decimal = Decimal("1"), anchor_price: Decimal = Decimal("0")):
        """
        Initialize the position map with a buffer of units.

        Args:
            initial_unit: Starting unit (usually 0)
            unit_size: Dollar amount per unit
            anchor_price: Price at unit 0
        """
        self.unit_size = unit_size
        self.anchor_price = anchor_price
        self.map: Dict[int, UnitLevel] = {}

        # Order ID Map for fast lookups
        self.order_id_map: Dict[str, int] = {}

        # Initialize with a buffer of units
        buffer_range = 20  # Initialize -20 to +20 units
        for unit in range(initial_unit - buffer_range, initial_unit + buffer_range + 1):
            price = self._calculate_unit_price(unit)
            self.map[unit] = UnitLevel(unit=unit, price=price)

        logger.info(f"PositionMap initialized with units [{initial_unit - buffer_range}, {initial_unit + buffer_range}]")

    def _calculate_unit_price(self, unit: int) -> Decimal:
        """Calculate the price for a specific unit"""
        return self.anchor_price + (Decimal(unit) * self.unit_size)

    def _ensure_unit_exists(self, unit: int) -> None:
        """Ensure a unit exists in the map, expanding if necessary"""
        if unit not in self.map:
            price = self._calculate_unit_price(unit)
            self.map[unit] = UnitLevel(unit=unit, price=price)
            logger.debug(f"Expanded PositionMap to include unit {unit}")

    def add_order(self, unit: int, order_id: str, order_type: str, size: Decimal) -> None:
        """
        Add a new order to the position map.

        Args:
            unit: Unit level where order is placed
            order_id: Unique order identifier
            order_type: "buy" or "sell"
            size: Order size in base currency
        """
        self._ensure_unit_exists(unit)

        # Add to unit level
        self.map[unit].add_order(order_id, order_type, size)

        # Add to order ID map for fast lookup
        self.order_id_map[order_id] = unit

        logger.debug(f"Added {order_type} order {order_id} at unit {unit}")

    def update_order_status(self, order_id: str, status: str, fill_price: Optional[Decimal] = None) -> bool:
        """
        Update the status of an order using the order ID map for fast lookup.

        Args:
            order_id: Order identifier
            status: New status ("filled", "cancelled", etc.)
            fill_price: Execution price if filled

        Returns:
            True if order was found and updated, False otherwise
        """
        # Fast lookup using order ID map
        if order_id not in self.order_id_map:
            logger.warning(f"Order {order_id} not found in OrderIDMap")
            return False

        unit = self.order_id_map[order_id]
        success = self.map[unit].update_order_status(order_id, status, fill_price)

        if success:
            logger.debug(f"Updated order {order_id} at unit {unit} to status: {status}")
            if status in ["filled", "cancelled"]:
                # Remove from order ID map as it's no longer active
                del self.order_id_map[order_id]
        else:
            logger.warning(f"Order {order_id} not found at unit {unit}")

        return success

    def get_unit_history(self, unit: int) -> Optional[UnitLevel]:
        """Get all order history for a specific unit"""
        return self.map.get(unit)

    def get_active_orders_at_unit(self, unit: int) -> List[OrderRecord]:
        """Get all active orders at a specific unit"""
        if unit in self.map:
            return self.map[unit].get_active_orders()
        return []

    def get_all_active_orders(self) -> Dict[int, List[OrderRecord]]:
        """Get all active orders across all units"""
        active_orders = {}
        for unit, level in self.map.items():
            active = level.get_active_orders()
            if active:
                active_orders[unit] = active
        return active_orders

    def get_order_by_id(self, order_id: str) -> Optional[tuple[int, OrderRecord]]:
        """
        Find an order by its ID.

        Returns:
            Tuple of (unit, OrderRecord) if found, None otherwise
        """
        if order_id not in self.order_id_map:
            return None

        unit = self.order_id_map[order_id]
        for order in self.map[unit].orders:
            if order.order_id == order_id:
                return (unit, order)
        return None

    def get_stats(self) -> dict:
        """Get statistics about the position map"""
        total_orders = sum(len(level.orders) for level in self.map.values())
        active_orders = len(self.order_id_map)
        filled_orders = sum(
            sum(1 for o in level.orders if o.status == "filled")
            for level in self.map.values()
        )

        return {
            "total_units": len(self.map),
            "total_orders": total_orders,
            "active_orders": active_orders,
            "filled_orders": filled_orders,
            "unit_range": (min(self.map.keys()), max(self.map.keys()))
        }

    def get_last_filled_order(self) -> Optional[tuple[int, OrderRecord]]:
        """Get the most recently filled order"""
        latest_fill = None
        latest_unit = None
        latest_time = None

        for unit, level in self.map.items():
            for order in level.orders:
                if order.status == "filled" and order.fill_timestamp:
                    if latest_time is None or order.fill_timestamp > latest_time:
                        latest_fill = order
                        latest_unit = unit
                        latest_time = order.fill_timestamp

        if latest_fill:
            return (latest_unit, latest_fill)
        return None