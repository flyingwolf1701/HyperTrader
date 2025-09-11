"""
Order Manager for HyperTrader Long Wallet
Manages all order operations including placement, cancellation, and tracking
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from loguru import logger
from .data_models import (
    OrderType, PositionConfig, ExecutionStatus, 
    OrderFillEvent, Phase
)


class OrderManager:
    """
    Manages all order operations for the long wallet strategy.
    Interfaces with the SDK to place, cancel, and track orders.
    """
    
    def __init__(self, sdk_client, symbol: str):
        """
        Initialize the order manager.
        
        Args:
            sdk_client: HyperliquidClient instance for API calls
            symbol: Trading symbol (e.g., "ETH")
        """
        self.sdk_client = sdk_client
        self.symbol = symbol
        
        # Track active orders by order_id
        self.active_orders: Dict[str, PositionConfig] = {}
        
        # Track orders by unit for quick lookup
        self.orders_by_unit: Dict[int, PositionConfig] = {}
        
        # Statistics
        self.total_orders_placed = 0
        self.total_orders_filled = 0
        self.total_orders_cancelled = 0
    
    async def place_stop_loss_order(self, 
                                   unit: int, 
                                   trigger_price: Decimal, 
                                   size: Decimal) -> Optional[str]:
        """
        Place a stop-loss sell order.
        
        Args:
            unit: Unit level for this order
            trigger_price: Price at which stop-loss triggers
            size: Size in asset terms (e.g., ETH amount)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            # Place stop order via SDK
            result = await self.sdk_client.place_stop_order(
                symbol=self.symbol,
                is_buy=False,  # Stop-loss is always a sell
                size=size,
                trigger_price=trigger_price,
                reduce_only=True  # Stop-losses reduce position only
            )
            
            if result.success:
                # Create position config for tracking
                config = PositionConfig(
                    unit=unit,
                    price=trigger_price,
                    order_id=result.order_id,
                    order_type=OrderType.STOP_LOSS_SELL,
                    execution_status=ExecutionStatus.PENDING
                )
                config.set_active_order(
                    result.order_id, 
                    OrderType.STOP_LOSS_SELL,
                    "stop_loss_orders"
                )
                
                # Track order
                self.active_orders[result.order_id] = config
                self.orders_by_unit[unit] = config
                self.total_orders_placed += 1
                
                logger.info(f"Placed STOP-LOSS at unit {unit}: {size:.6f} @ ${trigger_price:.2f} (ID: {result.order_id})")
                return result.order_id
            else:
                logger.error(f"Failed to place stop-loss at unit {unit}: {result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Exception placing stop-loss order: {e}")
            return None
    
    async def place_limit_buy_order(self, 
                                   unit: int, 
                                   price: Decimal, 
                                   size: Decimal) -> Optional[str]:
        """
        Place a limit buy order.
        
        Args:
            unit: Unit level for this order
            price: Limit price for the order
            size: Size in asset terms (e.g., ETH amount)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            # Place limit order via SDK
            result = await self.sdk_client.place_limit_order(
                symbol=self.symbol,
                is_buy=True,
                price=price,
                size=size,
                reduce_only=False,
                post_only=True  # Maker orders only to avoid fees
            )
            
            if result.success:
                # Create position config for tracking
                config = PositionConfig(
                    unit=unit,
                    price=price,
                    order_id=result.order_id,
                    order_type=OrderType.LIMIT_BUY,
                    execution_status=ExecutionStatus.PENDING
                )
                config.set_active_order(
                    result.order_id,
                    OrderType.LIMIT_BUY,
                    "limit_buy_orders"
                )
                
                # Track order
                self.active_orders[result.order_id] = config
                self.orders_by_unit[unit] = config
                self.total_orders_placed += 1
                
                logger.info(f"Placed LIMIT BUY at unit {unit}: {size:.6f} @ ${price:.2f} (ID: {result.order_id})")
                return result.order_id
            else:
                logger.error(f"Failed to place limit buy at unit {unit}: {result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Exception placing limit buy order: {e}")
            return None
    
    async def place_market_buy_order(self, size: Decimal) -> Optional[str]:
        """
        Place a market buy order (used for initial position entry).
        
        Args:
            size: Size in asset terms
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            # Get current price for USD calculation
            current_price = await self.sdk_client.get_current_price(self.symbol)
            usd_amount = size * current_price
            
            # Place market order via SDK
            result = await self.sdk_client.open_position(
                symbol=self.symbol,
                usd_amount=usd_amount,
                is_long=True,
                leverage=1,  # Will be set by SDK based on account settings
                slippage=0.01  # 1% slippage tolerance
            )
            
            if result.success:
                logger.info(f"Placed MARKET BUY: {size:.6f} @ ~${current_price:.2f} (ID: {result.order_id})")
                return result.order_id
            else:
                logger.error(f"Failed to place market buy: {result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Exception placing market buy order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            True if successful
        """
        try:
            # Cancel via SDK
            success = await self.sdk_client.cancel_order(self.symbol, order_id)
            
            if success:
                # Update tracking
                if order_id in self.active_orders:
                    config = self.active_orders[order_id]
                    config.mark_cancelled()
                    
                    # Remove from tracking
                    del self.active_orders[order_id]
                    if config.unit in self.orders_by_unit:
                        del self.orders_by_unit[config.unit]
                    
                    self.total_orders_cancelled += 1
                    logger.info(f"Cancelled order at unit {config.unit} (ID: {order_id})")
                
                return True
            else:
                logger.error(f"Failed to cancel order {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Exception cancelling order: {e}")
            return False
    
    async def cancel_order_at_unit(self, unit: int) -> bool:
        """
        Cancel order at a specific unit level.
        
        Args:
            unit: Unit level where order should be cancelled
            
        Returns:
            True if successful
        """
        if unit in self.orders_by_unit:
            config = self.orders_by_unit[unit]
            if config.order_id:
                return await self.cancel_order(config.order_id)
        
        logger.warning(f"No order found at unit {unit} to cancel")
        return False
    
    async def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.
        
        Returns:
            Number of orders cancelled
        """
        cancelled_count = 0
        order_ids = list(self.active_orders.keys())
        
        for order_id in order_ids:
            if await self.cancel_order(order_id):
                cancelled_count += 1
        
        logger.info(f"Cancelled {cancelled_count} orders")
        return cancelled_count
    
    def handle_order_fill(self, 
                         order_id: str, 
                         filled_price: Decimal, 
                         filled_size: Decimal,
                         current_phase: Phase) -> Optional[OrderFillEvent]:
        """
        Process an order fill notification.
        
        Args:
            order_id: ID of filled order
            filled_price: Execution price
            filled_size: Executed size
            current_phase: Current strategy phase
            
        Returns:
            OrderFillEvent if order was tracked, None otherwise
        """
        if order_id in self.active_orders:
            config = self.active_orders[order_id]
            
            # Mark as filled
            config.mark_filled(filled_price, filled_size)
            
            # Create fill event
            fill_event = OrderFillEvent(
                order_id=order_id,
                order_type=config.order_type,
                unit=config.unit,
                filled_price=filled_price,
                filled_size=filled_size,
                timestamp=datetime.now(),
                phase_before=current_phase
            )
            
            # Remove from active tracking
            del self.active_orders[order_id]
            if config.unit in self.orders_by_unit:
                del self.orders_by_unit[config.unit]
            
            self.total_orders_filled += 1
            
            logger.info(f"Order filled at unit {config.unit}: {config.order_type.value} "
                       f"{filled_size:.6f} @ ${filled_price:.2f}")
            
            return fill_event
        
        logger.warning(f"Received fill for untracked order: {order_id}")
        return None
    
    async def place_order_by_type(self,
                                 unit: int,
                                 order_type: OrderType,
                                 price: Decimal,
                                 size: Decimal) -> Optional[str]:
        """
        Place an order of specified type.
        
        Args:
            unit: Unit level for order
            order_type: Type of order to place
            price: Price for the order
            size: Size in asset terms
            
        Returns:
            Order ID if successful
        """
        if order_type == OrderType.STOP_LOSS_SELL:
            return await self.place_stop_loss_order(unit, price, size)
        elif order_type == OrderType.LIMIT_BUY:
            return await self.place_limit_buy_order(unit, price, size)
        elif order_type == OrderType.MARKET_BUY:
            return await self.place_market_buy_order(size)
        else:
            logger.error(f"Unsupported order type: {order_type}")
            return None
    
    def get_active_orders_summary(self) -> Dict:
        """
        Get summary of all active orders.
        
        Returns:
            Dictionary with order statistics and details
        """
        stop_losses = []
        limit_buys = []
        
        for config in self.active_orders.values():
            order_info = {
                'unit': config.unit,
                'price': float(config.price),
                'order_id': config.order_id
            }
            
            if config.order_type == OrderType.STOP_LOSS_SELL:
                stop_losses.append(order_info)
            elif config.order_type == OrderType.LIMIT_BUY:
                limit_buys.append(order_info)
        
        return {
            'total_active': len(self.active_orders),
            'stop_loss_orders': sorted(stop_losses, key=lambda x: x['unit']),
            'limit_buy_orders': sorted(limit_buys, key=lambda x: x['unit']),
            'total_placed': self.total_orders_placed,
            'total_filled': self.total_orders_filled,
            'total_cancelled': self.total_orders_cancelled
        }
    
    def get_order_at_unit(self, unit: int) -> Optional[PositionConfig]:
        """
        Get order configuration at a specific unit.
        
        Args:
            unit: Unit level to check
            
        Returns:
            PositionConfig if order exists at unit
        """
        return self.orders_by_unit.get(unit)
    
    def has_order_at_unit(self, unit: int) -> bool:
        """
        Check if an order exists at a specific unit.
        
        Args:
            unit: Unit level to check
            
        Returns:
            True if order exists at unit
        """
        return unit in self.orders_by_unit
    
    async def reconcile_orders(self, expected_orders: List[Tuple[int, OrderType]]) -> int:
        """
        Reconcile actual orders with expected orders.
        Cancel unexpected orders and return count of missing orders.
        
        Args:
            expected_orders: List of (unit, order_type) that should exist
            
        Returns:
            Number of missing orders that need to be placed
        """
        expected_units = {unit for unit, _ in expected_orders}
        actual_units = set(self.orders_by_unit.keys())
        
        # Cancel unexpected orders
        unexpected_units = actual_units - expected_units
        for unit in unexpected_units:
            logger.warning(f"Cancelling unexpected order at unit {unit}")
            await self.cancel_order_at_unit(unit)
        
        # Count missing orders
        missing_units = expected_units - actual_units
        
        return len(missing_units)