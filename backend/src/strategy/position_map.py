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
    status: str  # "active", "filled", "cancelled", "assumed_filled"
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
                # If we get an official 'filled' status for an order we already assumed was filled,
                # we just update the final fill price and timestamp. Otherwise, we set the new status.
                if order.status == "assumed_filled" and status == "filled":
                    pass  # The order is already considered filled by the strategy logic.
                else:
                    order.status = status
                
                if status == "filled" and fill_price:
                    order.fill_price = fill_price
                    order.fill_timestamp = datetime.now()
                return True
        return False

    def get_active_orders(self) -> List[OrderRecord]:
        """Get all orders with status 'active' at this level"""
        return [o for o in self.orders if o.status == "active"]

    def update_last_active_order_status(self, status: str) -> Optional[str]:
        """
        Finds the most recent 'active' order, updates its status, and returns its ID.
        This is used to mark an order as 'assumed_filled'.
        """
        # Iterate backwards to find the last appended 'active' order
        for order in reversed(self.orders):
            if order.status == "active":
                order.status = status
                return order.order_id
        return None


class PositionMap:
    """
    Primary historical ledger for the system.
    Dictionary where each key is a unit and value contains price and order history.
    """

    def __init__(self, unit_size_usd: Decimal, anchor_price: Decimal):
        """
        Initialize the position map with a buffer of units.

        Args:
            unit_size_usd: Dollar amount per unit
            anchor_price: Price at unit 0 (anchor is always at unit 0)
        """
        self.unit_size_usd = unit_size_usd
        self.anchor_price = anchor_price
        self.map: Dict[int, UnitLevel] = {}

        # Order ID Map for fast lookups of active/cancellable orders
        self.order_id_map: Dict[str, int] = {}

        # Initialize with a buffer of units centered at unit 0
        buffer_range = 20  # Initialize -20 to +20 units
        for unit in range(-buffer_range, buffer_range + 1):
            price = self._calculate_unit_price(unit)
            self.map[unit] = UnitLevel(unit=unit, price=price)

        logger.info(f"PositionMap initialized with units [-{buffer_range}, {buffer_range}]")

    def _calculate_unit_price(self, unit: int) -> Decimal:
        """Calculate the price for a specific unit"""
        return self.anchor_price + (Decimal(unit) * self.unit_size_usd)

    def _ensure_unit_exists(self, unit: int) -> None:
        """Ensure a unit exists in the map, expanding if necessary"""
        if unit not in self.map:
            price = self._calculate_unit_price(unit)
            self.map[unit] = UnitLevel(unit=unit, price=price)
            logger.info(f"Expanded PositionMap to include unit {unit}")

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

        logger.info(f"Added {order_type} order {order_id} at unit {unit}")

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
        unit = self.order_id_map.get(order_id)
        success = False

        if unit is not None:
            # Found in the fast-lookup map
            success = self.map[unit].update_order_status(order_id, status, fill_price)
        else:
            # Fallback: search all units if not in the map.
            # This is necessary for official fills of orders that were 'assumed_filled'.
            for u, level in self.map.items():
                if level.update_order_status(order_id, status, fill_price):
                    unit = u
                    success = True
                    break

        if success:
            logger.info(f"Updated order {order_id} at unit {unit} to status: {status}")
            # If an order is officially confirmed as inactive, remove it from the fast-lookup map.
            if status in ["filled", "cancelled"]:
                if order_id in self.order_id_map:
                    del self.order_id_map[order_id]
        else:
            logger.warning(f"Order {order_id} not found in PositionMap to update status to {status}")

        return success

    def update_assumed_fill(self, unit: int) -> None:
        """
        Find the latest active order at a unit and mark it as 'assumed_filled'.
        """
        if unit not in self.map:
            logger.warning(f"Attempted to assume fill for non-existent unit {unit}")
            return

        updated_order_id = self.map[unit].update_last_active_order_status("assumed_filled")
        
        if updated_order_id:
            logger.info(f"Marked order {updated_order_id} at unit {unit} as 'assumed_filled'")
            # Remove from the fast-lookup map. The bot's logic will no longer manage this order.
            # It is now considered 'in-flight' and waiting for an official 'filled' confirmation.
            if updated_order_id in self.order_id_map:
                del self.order_id_map[updated_order_id]
        else:
            logger.warning(f"Could not find an active order to mark as 'assumed_filled' at unit {unit}")

    def get_unit_history(self, unit: int) -> Optional[UnitLevel]:
        """Get all order history for a specific unit"""
        return self.map.get(unit)

    def get_active_orders_at_unit(self, unit: int) -> List[OrderRecord]:
        """Get all active orders at a specific unit"""
        if unit in self.map:
            return self.map[unit].get_active_orders()
        return []

    def has_active_order_at_unit(self, unit: int) -> bool:
        """Check if there are any active orders at a specific unit"""
        return len(self.get_active_orders_at_unit(unit)) > 0

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
        This now only searches through orders the bot considers active.
        """
        unit = self.order_id_map.get(order_id)
        if unit is None:
            return None

        for order in self.map[unit].orders:
            if order.order_id == order_id:
                return (unit, order)
        return None

    def get_stats(self) -> dict:
        """Get statistics about the position map"""
        total_orders = sum(len(level.orders) for level in self.map.values())
        active_orders_in_map = len(self.order_id_map)
        
        filled_count = 0
        assumed_filled_count = 0
        for level in self.map.values():
            for o in level.orders:
                if o.status == "filled":
                    filled_count += 1
                elif o.status == "assumed_filled":
                    assumed_filled_count += 1

        return {
            "total_units_tracked": len(self.map),
            "total_orders_placed": total_orders,
            "active_orders_managed": active_orders_in_map,
            "confirmed_fills": filled_count,
            "assumed_fills": assumed_filled_count,
            "unit_range": (min(self.map.keys()), max(self.map.keys())) if self.map else (0, 0)
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
