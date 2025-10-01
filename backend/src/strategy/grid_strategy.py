"""
Long-Biased Grid Trading Strategy v11.2.0
Main strategy implementation with event-driven grid management.
"""

import asyncio
from decimal import Decimal
from typing import List, Optional, Dict
from datetime import datetime
from loguru import logger

from ..exchange.hyperliquid_sdk import HyperliquidClient, OrderResult
from ..exchange.hyperliquid_sdk_websocket import HyperliquidSDKWebSocketClient
from .unit_tracker import UnitTracker, UnitChangeEvent, Direction
from .position_map import PositionMap
from .data_models import StrategyConfig, StrategyMetrics, StrategyState


class GridTradingStrategy:
    """
    Long-biased grid trading strategy with whipsaw resistance.
    Maintains 4 active orders trailing the current price.
    """

    def __init__(self, config: StrategyConfig, client: HyperliquidClient, websocket: HyperliquidSDKWebSocketClient):
        """
        Initialize the grid trading strategy.

        Args:
            config: Strategy configuration
            client: HyperliquidClient for order execution
            websocket: WebSocket client for real-time data
        """
        self.config = config
        self.client = client
        self.websocket = websocket

        # Strategy state
        self.state = StrategyState.INITIALIZING
        self.metrics = StrategyMetrics(initial_position_value_usd=config.position_value_usd)
        self.is_shutting_down = False

        # Core components (will be initialized after initial position)
        self.unit_tracker: Optional[UnitTracker] = None
        self.position_map: Optional[PositionMap] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

        # Active order tracking. These lists operate as queues:
        # - FILLED orders are LIFO (last one in is closest to price, so first one out).
        # - CANCELLED orders are FIFO (first one in is furthest from price, so it's removed).
        self.trailing_stop: List[int] = []  # Queue of active sell order units
        self.trailing_buy: List[int] = []   # Queue of active buy order units

        # Position fragment tracking (0-4 scale)
        # 4 = fully invested, 3 = 1/4 sold (need 1 buy), 0 = fully sold (need 4 buys)
        self.fragments_invested: int = 0

        # Whipsaw detection
        self.whipsaw_paused = False
        self.whipsaw_resolution_pending = False

        logger.info(f"Grid Trading Strategy initialized for {config.symbol}")
        logger.info(f"Configuration: Leverage={config.leverage}x, Unit Size=${config.unit_size_usd}, "
                   f"Position=${config.position_value_usd}, Margin=${config.margin_required}")

    async def initialize(self) -> bool:
        """
        Initialize the strategy: establish position and place initial grid.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info(f"Initializing strategy for {self.config.symbol}...")

            # Store the main event loop for later use
            self.main_loop = asyncio.get_running_loop()

            # Set leverage
            if not self.client.set_leverage(self.config.symbol, self.config.leverage):
                logger.error("Failed to set leverage")
                return False

            # Cancel any existing orders
            cancelled = self.client.cancel_all_orders(self.config.symbol)
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} existing orders")

            # Get current price
            current_price = self.client.get_current_price(self.config.symbol)
            logger.info(f"Current {self.config.symbol} price: ${current_price:.2f}")

            # Open initial position
            logger.info(f"Opening initial position: ${self.config.position_value_usd} @ {self.config.leverage}x (margin: ${self.config.margin_required})")
            result = self.client.open_position(
                symbol=self.config.symbol,
                usd_amount=self.config.position_value_usd,
                is_long=True,
                leverage=self.config.leverage,
                slippage=0.01
            )

            if not result.success:
                logger.error(f"Failed to open initial position: {result.error_message}")
                return False

            # Record execution details
            self.metrics.current_position_size = result.filled_size
            self.metrics.avg_entry_price = result.average_price
            anchor_price = result.average_price

            # Set fragments_invested to 4 (fully invested)
            self.fragments_invested = 4

            logger.success(f"Initial position established: {result.filled_size} {self.config.symbol} @ ${anchor_price:.2f} | Fragments: 4/4")

            # Initialize unit tracker with anchor price
            self.unit_tracker = UnitTracker(
                unit_size_usd=self.config.unit_size_usd,
                anchor_price=anchor_price
            )

            # Initialize position map
            self.position_map = PositionMap(
                unit_size_usd=self.config.unit_size_usd,
                anchor_price=anchor_price
            )

            # Register unit change callback
            self.unit_tracker.on_unit_change = self._on_unit_change

            # Place initial grid (4 sell orders below current unit)
            if not await self._place_initial_grid():
                logger.error("Failed to establish initial grid - aborting initialization")
                return False

            # Subscribe to websocket feeds
            await self._setup_websocket_subscriptions()

            self.state = StrategyState.RUNNING
            logger.success(f"Strategy initialization complete for {self.config.symbol}")
            return True

        except Exception as e:
            logger.error(f"Strategy initialization failed: {e}")
            self.state = StrategyState.STOPPED
            return False

    async def _place_initial_grid(self) -> bool:
        """
        Place the initial 4 sell orders below current price.

        Returns:
            True if all orders placed successfully, False otherwise
        """
        logger.info("Placing initial grid orders...")

        # Place 4 sell orders at units -1, -2, -3, -4
        initial_units = [-1, -2, -3, -4]
        for unit in initial_units:
            price = self.unit_tracker.get_unit_price(unit)

            # Calculate sell fragment (1/4 of position)
            fragment_size = self.metrics.current_position_size / 4

            logger.info(f"Placing sell order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}")

            result = self.client.place_limit_order(
                symbol=self.config.symbol,
                is_buy=False,
                price=price,
                size=fragment_size,
                reduce_only=False
            )

            if result.success:
                # Track the order
                self.trailing_stop.append(unit)
                self.position_map.add_order(unit, result.order_id, "sell", fragment_size)
                logger.info(f"Sell order placed at unit {unit}: {result.order_id}")
            else:
                logger.error(f"Failed to place sell order at unit {unit}: {result.error_message}")
                return False  # Abort on first failure
        
        # The list is currently [-1, -2, -3, -4]. We reverse it to [-4, -3, -2, -1]
        # so the oldest/furthest order (-4) is at the front of the queue (index 0)
        # for easy cancellation using pop(0).
        self.trailing_stop.reverse()
        logger.success(f"Initial grid established: {len(self.trailing_stop)} sell orders active at units {self.trailing_stop}")
        return True

    async def _setup_websocket_subscriptions(self) -> None:
        """Subscribe to websocket feeds for price updates and fills."""
        # Create fill callback that properly handles async calls
        async def fill_handler(order_id: str, price: Decimal, size: Decimal):
            """Handle fill confirmations from WebSocket"""
            logger.info(f"Fill handler triggered for order {order_id}")
            await self.process_fill_confirmation(order_id, price, size)

        # Subscribe to price updates AND register fill callback
        await self.websocket.subscribe_to_trades(
            symbol=self.config.symbol,
            price_callback=self._on_price_update,
            fill_callback=fill_handler
        )

        # Subscribe to user fills (this triggers the fill_callback registered above)
        wallet_address = self.client.get_user_address()
        await self.websocket.subscribe_to_user_fills(wallet_address)

        # Subscribe to order updates for real-time order tracking
        await self.websocket.subscribe_to_order_updates(wallet_address)

        logger.info(f"Subscribed to {self.config.symbol} price feed, order fills, and order updates")

    def _on_price_update(self, price: Decimal) -> None:
        """
        Handle real-time price updates.

        Args:
            price: Current market price
        """
        if self.unit_tracker:
            # Update unit tracker which will trigger unit change events if needed
            self.unit_tracker.update_price(price)

    def _on_unit_change(self, event: UnitChangeEvent) -> None:
        """
        Handle unit change events from the unit tracker.

        Args:
            event: UnitChangeEvent containing unit transition details
        """
        # Don't process events during shutdown
        if self.is_shutting_down:
            return

        # Schedule the async handler in the main event loop
        if self.main_loop and self.main_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._handle_unit_change(event), self.main_loop)
        else:
            if not self.is_shutting_down:
                logger.error("Main event loop not available or not running!")

    async def _handle_unit_change(self, event: UnitChangeEvent) -> None:
        """
        Async handler for unit change events.
        Processes unit changes one by one to handle gaps and ensure correct order placement.

        Args:
            event: UnitChangeEvent containing unit transition details
        """
        logger.info(
            f"Unit Change: {event.previous_unit} -> {event.current_unit} | "
            f"Fragments: {self.fragments_invested}/4 | "
            f"Sells: {len(self.trailing_stop)} {self.trailing_stop} | "
            f"Buys: {len(self.trailing_buy)} {self.trailing_buy}"
        )

        current = event.current_unit
        previous = event.previous_unit

        # --- Process Unit Changes Sequentially ---
        if current > previous:
            # Price went UP
            for unit in range(previous + 1, current + 1):
                await self._process_unit_up(unit)
        elif current < previous:
            # Price went DOWN
            for unit in range(previous - 1, current - 1, -1):
                await self._process_unit_down(unit)

    def _has_order_at_unit_on_exchange(self, unit: int) -> bool:
        """
        Check if Hyperliquid actually has an active order at this unit.
        This is the source of truth, not our internal tracking.
        """
        try:
            open_orders = self.client.get_open_orders(self.config.symbol)
            target_price = self.unit_tracker.get_unit_price(unit)

            # Calculate proper tolerance based on actual price gap between units
            # For ETH at $2000 with $0.5 unit: unit_price_gap = $0.5 / ($2000/1) = ~$0.00025
            # We use half the unit gap as tolerance to avoid matching adjacent units
            unit_0_price = self.unit_tracker.get_unit_price(0)
            unit_1_price = self.unit_tracker.get_unit_price(1)
            unit_price_gap = abs(unit_1_price - unit_0_price)
            tolerance = unit_price_gap / Decimal("2")  # Half a unit gap

            logger.debug(f"🔍 Checking unit {unit}: target=${target_price:.4f}, tolerance=±${tolerance:.4f}")
            logger.debug(f"📊 Open orders on exchange: {len(open_orders)}")

            # Check if any order matches this unit's price (within tolerance)
            for order in open_orders:
                order_price = Decimal(str(order.get("limitPx", 0)))
                price_diff = abs(order_price - target_price)
                side = order.get("side", "?")
                oid = order.get("oid", "?")

                logger.debug(f"   Order {oid}: ${order_price:.4f} ({side}) | diff=${price_diff:.4f}")

                if price_diff < tolerance:
                    logger.warning(f"✅ Found existing order at unit {unit}: {oid} @ ${order_price:.4f} (within ±${tolerance:.4f})")
                    return True

            logger.info(f"❌ No order found at unit {unit} @ ${target_price:.4f}")
            return False
        except Exception as e:
            logger.error(f"Error checking orders at unit {unit}: {e}")
            return False  # If we can't check, assume no order exists

    async def _process_unit_up(self, current_unit: int) -> None:
        """
        Process a single unit move UP. This is a TRENDING UP move.
        Always place trailing sell, let duplicates happen if our tracking is wrong.

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.warning(f"⬆️ PROCESSING UP to unit {current_unit}")

        # 1. Place new stop-loss sell order at current_unit - 1
        new_sell_unit = current_unit - 1

        logger.info(f"🎯 Want to place SELL at unit {new_sell_unit}. Current tracking: {self.trailing_stop}")

        # Check Hyperliquid's actual orders (source of truth)
        has_order = self._has_order_at_unit_on_exchange(new_sell_unit)
        logger.warning(f"🔍 Exchange check result for unit {new_sell_unit}: {'HAS ORDER' if has_order else 'NO ORDER'}")

        if not has_order:
            logger.warning(f"📤 PLACING new SELL at unit {new_sell_unit}")
            result = await self._place_sell_order_at_unit(new_sell_unit)
            if result:
                self.trailing_stop.append(new_sell_unit)
                logger.success(f"✅ Placed new SELL at unit {new_sell_unit}. Active sells: {self.trailing_stop}")
            else:
                logger.error(f"❌ Failed to place SELL at unit {new_sell_unit}")
                return
        else:
            logger.info(f"⏭️ Skipping SELL at unit {new_sell_unit} - order exists on Hyperliquid")

        # 2. Cancel oldest stop if we have more than 4
        if len(self.trailing_stop) > 4:
            oldest_unit = self.trailing_stop.pop(0)
            logger.warning(f"🗑️ Cancelling oldest SELL at unit {oldest_unit} (have {len(self.trailing_stop)+1} sells)")
            await self._cancel_orders_at_unit(oldest_unit)

    async def _process_unit_down(self, current_unit: int) -> None:
        """
        Process a single unit move DOWN.
        Always place trailing buy, let duplicates happen if our tracking is wrong.

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.warning(f"⬇️ PROCESSING DOWN to unit {current_unit}")

        # 1. Place new stop-entry buy order at current_unit + 1
        new_buy_unit = current_unit + 1

        logger.info(f"🎯 Want to place BUY at unit {new_buy_unit}. Current tracking: {self.trailing_buy}")

        # Check Hyperliquid's actual orders (source of truth)
        has_order = self._has_order_at_unit_on_exchange(new_buy_unit)
        logger.warning(f"🔍 Exchange check result for unit {new_buy_unit}: {'HAS ORDER' if has_order else 'NO ORDER'}")

        if not has_order:
            # If we already have 4 buys, cancel the highest (index 0) BEFORE placing new one
            if len(self.trailing_buy) >= 4:
                highest_unit = self.trailing_buy.pop(0)
                logger.warning(f"🗑️ Cancelling highest BUY at unit {highest_unit} to make room for new one")
                await self._cancel_orders_at_unit(highest_unit)

            logger.warning(f"📤 PLACING new BUY at unit {new_buy_unit}")
            result = await self._place_buy_order_at_unit(new_buy_unit)
            if result:
                self.trailing_buy.append(new_buy_unit)
                logger.success(f"✅ Placed new BUY at unit {new_buy_unit}. Active buys: {self.trailing_buy}")
            else:
                logger.error(f"❌ Failed to place BUY at unit {new_buy_unit}")
                return
        else:
            logger.info(f"⏭️ Skipping BUY at unit {new_buy_unit} - order exists on Hyperliquid")

    async def _place_sell_order_at_unit(self, unit: int) -> Optional[str]:
        """
        Place a sell order at a specific unit.

        Args:
            unit: Unit level for the order

        Returns:
            Order ID if successful, None otherwise
        """
        price = self.unit_tracker.get_unit_price(unit)

        # Dynamic sell fragment calculation
        num_active_sells = len(self.trailing_stop) if self.trailing_stop else 1
        divisor = min(num_active_sells, 4)  # Cap at 4
        fragment_size = self.metrics.current_position_size / divisor

        logger.info(f"Placing SELL order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}")

        result = self.client.place_limit_order(
            symbol=self.config.symbol,
            is_buy=False,
            price=price,
            size=fragment_size,
            reduce_only=False
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "sell", fragment_size)
            logger.info(f"SELL order placed at unit {unit}: {result.order_id}")
            return result.order_id
        else:
            logger.error(f"Failed to place sell order: {result.error_message}")
            return None

    async def _place_buy_order_at_unit(self, unit: int) -> Optional[str]:
        """
        Place a buy order at a specific unit.

        Args:
            unit: Unit level for the order

        Returns:
            Order ID if successful, None otherwise
        """
        price = self.unit_tracker.get_unit_price(unit)

        # Use compounded fragment size for buys
        fragment_usd = self.metrics.new_buy_fragment
        fragment_size = self.client.calculate_position_size(self.config.symbol, fragment_usd)

        logger.info(f"Placing BUY order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}, value: ${fragment_usd:.2f}")

        result = self.client.place_stop_buy(
            symbol=self.config.symbol,
            size=fragment_size,
            trigger_price=price,
            limit_price=price,
            reduce_only=False
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "buy", fragment_size)
            logger.info(f"BUY order placed at unit {unit}: {result.order_id}")
            return result.order_id
        else:
            logger.error(f"Failed to place buy order: {result.error_message}")
            return None

    async def _cancel_orders_at_unit(self, unit: int) -> None:
        """
        Cancel all active orders at a specific unit.

        Args:
            unit: Unit level to cancel orders at
        """
        active_orders = self.position_map.get_active_orders_at_unit(unit)

        if not active_orders:
            logger.warning(f"Attempted to cancel orders at unit {unit}, but PositionMap found no active orders.")
            return

        for order in active_orders:
            logger.info(f"Cancelling {order.order_type} order {order.order_id} at unit {unit}")
            success = self.client.cancel_order(self.config.symbol, order.order_id)

            if success:
                self.position_map.update_order_status(order.order_id, "cancelled")
            else:
                logger.warning(f"Failed to cancel order {order.order_id}")

    async def cleanup_duplicate_orders(self) -> None:
        """
        Clean up any duplicate orders at the same unit.
        Keeps the most recent order, cancels the rest.
        """
        try:
            open_orders = self.client.get_open_orders(self.config.symbol)

            # Group orders by price
            orders_by_price = {}
            for order in open_orders:
                price = Decimal(str(order.get("limitPx", 0)))
                if price not in orders_by_price:
                    orders_by_price[price] = []
                orders_by_price[price].append(order)

            # Cancel duplicates (keep most recent)
            cancelled_count = 0
            for price, orders in orders_by_price.items():
                if len(orders) > 1:
                    logger.warning(f"Found {len(orders)} orders at price ${price} - keeping most recent")
                    # Sort by timestamp (most recent first)
                    sorted_orders = sorted(orders, key=lambda x: x.get("timestamp", 0), reverse=True)
                    # Cancel all except the first one
                    for order in sorted_orders[1:]:
                        order_id = str(order.get("oid"))
                        if self.client.cancel_order(self.config.symbol, order_id):
                            logger.info(f"Cancelled duplicate order {order_id} at ${price}")
                            cancelled_count += 1

            if cancelled_count > 0:
                logger.warning(f"Cleaned up {cancelled_count} duplicate orders")

        except Exception as e:
            logger.error(f"Failed to cleanup duplicates: {e}")

    async def process_fill_confirmation(self, order_id: str, price: Decimal, size: Decimal) -> None:
        """
        Process confirmed order fills from WebSocket.
        This replaces the assumed fill logic with actual confirmations.

        Args:
            order_id: The filled order ID
            price: Fill price
            size: Fill size
        """
        logger.info(f"Processing fill confirmation for order {order_id}")

        # Find the order in position map
        order_info = self.position_map.get_order_by_id(order_id)
        if not order_info:
            logger.warning(f"Fill confirmation for unknown order {order_id}")
            return

        unit, order_record = order_info

        # Update order status to filled
        self.position_map.update_order_status(order_id, "filled", price)

        # Handle based on order type
        if order_record.order_type == "sell":
            # Decrement fragments_invested (sold 1/4 of position)
            self.fragments_invested = max(0, self.fragments_invested - 1)
            logger.warning(f"SELL FILLED at ${price:.2f} | Fragments now: {self.fragments_invested}/4")

            # Remove from trailing_stop if present
            if unit in self.trailing_stop:
                self.trailing_stop.remove(unit)
                logger.info(f"Removed unit {unit} from trailing_stop after fill confirmation")

            # Place replacement buy order at current unit
            new_buy_unit = self.unit_tracker.current_unit
            if new_buy_unit not in self.trailing_buy and not self.position_map.has_active_order_at_unit(new_buy_unit):
                await self._place_buy_order_at_unit(new_buy_unit)
                self.trailing_buy.append(new_buy_unit)
                logger.info(f"Placed replacement BUY at unit {new_buy_unit}")

            # Cancel oldest buy if > 4
            if len(self.trailing_buy) > 4:
                oldest_unit = self.trailing_buy.pop(0)
                await self._cancel_orders_at_unit(oldest_unit)
                logger.info(f"Cancelled oldest BUY at unit {oldest_unit}")

        elif order_record.order_type == "buy":
            # Increment fragments_invested (bought back 1/4 of position)
            self.fragments_invested = min(4, self.fragments_invested + 1)
            logger.warning(f"BUY FILLED at ${price:.2f} | Fragments now: {self.fragments_invested}/4")

            # Remove from trailing_buy if present
            if unit in self.trailing_buy:
                self.trailing_buy.remove(unit)
                logger.info(f"Removed unit {unit} from trailing_buy after fill confirmation")

            # Place replacement sell order at current unit
            new_sell_unit = self.unit_tracker.current_unit
            if new_sell_unit not in self.trailing_stop and not self.position_map.has_active_order_at_unit(new_sell_unit):
                await self._place_sell_order_at_unit(new_sell_unit)
                self.trailing_stop.append(new_sell_unit)
                logger.info(f"Placed replacement SELL at unit {new_sell_unit}")

            # Cancel oldest sell if > 4
            if len(self.trailing_stop) > 4:
                oldest_unit = self.trailing_stop.pop(0)
                await self._cancel_orders_at_unit(oldest_unit)
                logger.info(f"Cancelled oldest SELL at unit {oldest_unit}")

        # Call the existing fill handler for metrics
        self._on_order_fill(order_id, price, size)

    def _on_order_fill(self, order_id: str, price: Decimal, size: Decimal) -> None:
        """
        Handle order fill notifications for metrics.

        Args:
            order_id: Filled order ID
            price: Fill price
            size: Fill size
        """
        logger.info(f"ORDER FILLED: {order_id} - {size:.4f} {self.config.symbol} @ ${price:.2f}")

        # Update position map
        self.position_map.update_order_status(order_id, "filled", price)

        # Find order details
        order_info = self.position_map.get_order_by_id(order_id)
        if order_info:
            unit, order_record = order_info

            # Update metrics based on order type
            if order_record.order_type == "sell":
                # Calculate PnL for this sell
                if self.metrics.avg_entry_price:
                    pnl = (price - self.metrics.avg_entry_price) * size
                    self.metrics.realized_pnl += pnl
                    self.metrics.total_trades += 1

                    if pnl > 0:
                        self.metrics.winning_trades += 1
                        logger.success(f"Profitable trade: +${pnl:.2f}")
                    else:
                        self.metrics.losing_trades += 1
                        logger.warning(f"Losing trade: -${abs(pnl):.2f}")

                # Update position size
                self.metrics.current_position_size -= size

            elif order_record.order_type == "buy":
                # Update position size
                self.metrics.current_position_size += size

                # Update average entry price
                if self.metrics.avg_entry_price:
                    total_cost = (self.metrics.avg_entry_price * (self.metrics.current_position_size - size)) + (price * size)
                    self.metrics.avg_entry_price = total_cost / self.metrics.current_position_size
                else:
                    self.metrics.avg_entry_price = price

        self._log_metrics()

    def _log_metrics(self) -> None:
        """Log current strategy metrics."""
        logger.info(
            f"Metrics: Position={self.metrics.current_position_size:.4f} "
            f"Realized PnL=${self.metrics.realized_pnl:.2f} "
            f"Trades={self.metrics.total_trades} "
            f"Win Rate={self.metrics.win_rate:.1f}%"
        )

    async def run(self) -> None:
        """
        Main strategy loop.
        Keeps the strategy running and handles shutdown.
        """
        logger.info(f"Starting main strategy loop for {self.config.symbol}...")

        # Track last cleanup time
        last_cleanup = asyncio.get_event_loop().time()

        try:
            while self.state == StrategyState.RUNNING:
                await asyncio.sleep(10)  # Main loop heartbeat

                # Cleanup duplicates every 60 seconds
                current_time = asyncio.get_event_loop().time()
                if current_time - last_cleanup >= 60:
                    await self.cleanup_duplicate_orders()
                    last_cleanup = current_time

        except KeyboardInterrupt:
            logger.warning("Strategy interrupted by user")
        except Exception as e:
            logger.error(f"Strategy error: {e}")
        finally:
            await self.shutdown()


    def get_diagnostic_status(self) -> dict:
        """
        Get detailed diagnostic status for debugging.

        Returns:
            Dictionary with current state and diagnostics
        """
        status = {
            "strategy_state": self.state.value if self.state else "NOT_INITIALIZED",
            "symbol": self.config.symbol,
        }
        
        if self.config and hasattr(self.config, 'unit_size'):
            status["unit_size"] = float(self.config.unit_size)
        else:
            status["unit_size"] = None


        if self.unit_tracker:
            status.update({
                "current_unit": self.unit_tracker.current_unit,
                "current_price": float(self.unit_tracker.current_price),
                "anchor_price": float(self.unit_tracker.anchor_price),
                "current_direction": self.unit_tracker.current_direction.value,
                "whipsaw_paused": self.whipsaw_paused,
            })
        else:
            status["unit_tracker"] = "NOT_INITIALIZED"

        status.update({
            "active_sells": self.trailing_stop,
            "active_buys": self.trailing_buy,
            "total_orders": len(self.trailing_stop) + len(self.trailing_buy),
            "position_size": float(self.metrics.current_position_size) if self.metrics else 0,
            "realized_pnl": float(self.metrics.realized_pnl) if self.metrics else 0,
        })

        return status

    async def shutdown(self) -> None:
        """Gracefully shutdown the strategy."""
        logger.warning(f"Shutting down strategy for {self.config.symbol}...")
        self.is_shutting_down = True
        self.state = StrategyState.STOPPING

        try:
            # Cancel all orders
            cancelled = self.client.cancel_all_orders(self.config.symbol)
            logger.info(f"Cancelled {cancelled} orders")

            # Log final metrics
            logger.info("Final Strategy Metrics:")
            logger.info(f"  Total Trades: {self.metrics.total_trades}")
            logger.info(f"  Win Rate: {self.metrics.win_rate:.1f}%")
            logger.info(f"  Realized PnL: ${self.metrics.realized_pnl:.2f}")
            logger.info(f"  Position Size: {self.metrics.current_position_size}")

            # Get position map stats
            if self.position_map:
                stats = self.position_map.get_stats()
                logger.info(f"  Position Map Stats: {stats}")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        self.state = StrategyState.STOPPED
        logger.info("Strategy shutdown complete")

