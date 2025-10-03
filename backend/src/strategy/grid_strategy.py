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

        # Whipsaw detection - simple pattern matching on last 3 units
        self.running_units: List[int] = []  # Track last 3 units for whipsaw detection
        self.whipsaw_active: bool = False   # True when in whipsaw protection mode
        self.whipsaw_range_min: int = 0     # Min unit when whipsaw detected
        self.whipsaw_range_max: int = 0     # Max unit when whipsaw detected

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
        current = event.current_unit
        previous = event.previous_unit

        # --- Whipsaw Detection ---
        # Track last 3 units
        self.running_units.append(current)
        if len(self.running_units) > 3:
            self.running_units.pop(0)

        # Detect whipsaw pattern: [5,4,5] or [4,5,4] - reversal pattern
        if len(self.running_units) == 3:
            if (self.running_units[0] == self.running_units[2] and
                self.running_units[1] != self.running_units[0]):
                if not self.whipsaw_active:
                    self.whipsaw_active = True
                    # Capture the oscillation range at detection time
                    self.whipsaw_range_min = min(self.running_units)
                    self.whipsaw_range_max = max(self.running_units)
                    logger.warning(f"🌀 WHIPSAW DETECTED! Pattern: {self.running_units}, Range: [{self.whipsaw_range_min}, {self.whipsaw_range_max}]")

        # Exit whipsaw when breaking out of the captured oscillation range
        exited_whipsaw_on_up = False
        if self.whipsaw_active:
            if current > self.whipsaw_range_max:
                logger.success(f"✅ Exiting whipsaw UP - broke above {self.whipsaw_range_max} at unit {current}")
                self.whipsaw_active = False
                exited_whipsaw_on_up = True
            elif current < self.whipsaw_range_min:
                logger.success(f"✅ Exiting whipsaw DOWN - broke below {self.whipsaw_range_min} at unit {current}")
                self.whipsaw_active = False

        logger.info(
            f"Unit Change: {previous} -> {current} | "
            f"Whipsaw: {'ACTIVE' if self.whipsaw_active else 'off'} | "
            f"Fragments: {self.fragments_invested}/4 | "
            f"Sells: {len(self.trailing_stop)} {self.trailing_stop} | "
            f"Buys: {len(self.trailing_buy)} {self.trailing_buy}"
        )

        # --- Process Unit Changes Sequentially ---
        if current > previous:
            # Price went UP
            for unit in range(previous + 1, current + 1):
                await self._process_unit_up(unit)

            # Catch-up logic when exiting whipsaw on UP move
            if exited_whipsaw_on_up:
                await self._catchup_sells_after_whipsaw(current)

        elif current < previous:
            # Price went DOWN
            for unit in range(previous - 1, current - 1, -1):
                await self._process_unit_down(unit)


    async def _process_unit_up(self, current_unit: int) -> None:
        """
        Process a single unit move UP - Price is RISING.

        Whipsaw protection logic:
        - If whipsaw active: place sells at [current-5, current-4, current-3, current-2]
        - Normal: place sell at current-1
        - Always maintain 4 total sells

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.warning(f"⬆️ UNIT UP to {current_unit}")

        if self.whipsaw_active:
            # Whipsaw protection: place sells further away at -5, -4, -3, -2
            logger.warning(f"🌀 Whipsaw - placing sells at {[current_unit-5, current_unit-4, current_unit-3, current_unit-2]}")
            target_units = [current_unit - 5, current_unit - 4, current_unit - 3, current_unit - 2]

            for unit in target_units:
                if unit not in self.trailing_stop:
                    result = await self._place_sell_order_at_unit(unit)
                    if result:
                        self.trailing_stop.append(unit)

            # Sort so oldest/furthest (most negative) is at index 0
            self.trailing_stop.sort()

            # Maintain 4 sells - cancel oldest if needed
            while len(self.trailing_stop) > 4:
                oldest_unit = self.trailing_stop.pop(0)
                await self._cancel_orders_at_unit(oldest_unit)
        else:
            # Normal operation: place sell at current-1
            new_sell_unit = current_unit - 1

            # Check if we already have this unit in our tracking list
            if new_sell_unit not in self.trailing_stop:
                result = await self._place_sell_order_at_unit(new_sell_unit)
                if result:
                    self.trailing_stop.append(new_sell_unit)
                    logger.success(f"✅ SELL placed at {new_sell_unit}. Sells: {self.trailing_stop}")
                else:
                    logger.error(f"❌ Failed to place SELL at {new_sell_unit}")
                    return

            # Cancel oldest sell if we have > 4
            if len(self.trailing_stop) > 4:
                oldest_unit = self.trailing_stop.pop(0)
                await self._cancel_orders_at_unit(oldest_unit)

    async def _process_unit_down(self, current_unit: int) -> None:
        """
        Process a single unit move DOWN - Price is FALLING.

        Whipsaw protection logic:
        - If whipsaw active: skip buy placement (avoid catching falling knife)
        - Normal: place buy at current+1, maintain 4 total buys

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.warning(f"⬇️ UNIT DOWN to {current_unit}")

        # Skip buy placement during whipsaw
        if self.whipsaw_active:
            logger.warning(f"🌀 Whipsaw - skipping BUY")
            return

        # Normal operation: place buy at current+1
        new_buy_unit = current_unit + 1

        # If we already have 4 buys, cancel highest BEFORE placing new one
        if len(self.trailing_buy) >= 4:
            highest_unit = self.trailing_buy.pop(0)
            await self._cancel_orders_at_unit(highest_unit)

        # Check if we already have this unit in our tracking list
        if new_buy_unit not in self.trailing_buy:
            result = await self._place_buy_order_at_unit(new_buy_unit)
            if result:
                self.trailing_buy.append(new_buy_unit)
                # Sort descending so highest/furthest is at index 0
                self.trailing_buy.sort(reverse=True)
                logger.success(f"✅ BUY placed at {new_buy_unit}. Buys: {self.trailing_buy}")
            else:
                logger.error(f"❌ Failed to place BUY at {new_buy_unit}")
                return

    async def _catchup_sells_after_whipsaw(self, current_unit: int) -> None:
        """
        Catch-up logic when exiting whipsaw on an UP move.
        Fills in missing sell orders between the furthest sell and current position.
        Example: If at unit 2 with sells at [-5,-4,-3,-2], add sells at [0,1] to get [-2,-1,0,1]

        Args:
            current_unit: The current unit level after breaking out of whipsaw
        """
        # Target: 4 sells at [current-4, current-3, current-2, current-1]
        # After exiting whipsaw upward, we want sells trailing immediately below
        target_units = [current_unit - 4, current_unit - 3, current_unit - 2, current_unit - 1]

        logger.info(f"Catch-up: Current sells {self.trailing_stop}, Target: {target_units}")

        # First, cancel any sells that are too far below (older than target range)
        # Sort current sells to identify oldest first
        self.trailing_stop.sort()

        # Remove sells that are below our target range
        min_target = min(target_units)
        to_remove = []
        for unit in self.trailing_stop:
            if unit < min_target:
                to_remove.append(unit)

        for unit in to_remove:
            self.trailing_stop.remove(unit)
            await self._cancel_orders_at_unit(unit)
            logger.info(f"Catch-up: Removed old sell at {unit}")

        # Now add missing sells in the target range
        for unit in target_units:
            if unit not in self.trailing_stop:
                result = await self._place_sell_order_at_unit(unit)
                if result:
                    self.trailing_stop.append(unit)
                    logger.info(f"Catch-up: Added sell at {unit}")

        # Sort so oldest/furthest (most negative) is at index 0
        self.trailing_stop.sort()

        # Final safety check - maintain exactly 4 sells
        while len(self.trailing_stop) > 4:
            oldest_unit = self.trailing_stop.pop(0)
            await self._cancel_orders_at_unit(oldest_unit)
            logger.warning(f"Catch-up: Safety removal of {oldest_unit}")

        logger.success(f"✅ Catch-up complete. Sells: {self.trailing_stop}")

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

        result = self.client.place_limit_order(
            symbol=self.config.symbol,
            is_buy=False,
            price=price,
            size=fragment_size,
            reduce_only=False
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "sell", fragment_size)
            return result.order_id
        else:
            logger.error(f"Failed to place sell order at {unit}: {result.error_message}")
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

        result = self.client.place_stop_buy(
            symbol=self.config.symbol,
            size=fragment_size,
            trigger_price=price,
            limit_price=price,
            reduce_only=False
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "buy", fragment_size)
            return result.order_id
        else:
            logger.error(f"Failed to place buy order at {unit}: {result.error_message}")
            return None

    async def _cancel_orders_at_unit(self, unit: int) -> None:
        """
        Cancel all active orders at a specific unit.

        Args:
            unit: Unit level to cancel orders at
        """
        active_orders = self.position_map.get_active_orders_at_unit(unit)

        if not active_orders:
            return

        for order in active_orders:
            success = self.client.cancel_order(self.config.symbol, order.order_id)

            if success:
                self.position_map.update_order_status(order.order_id, "cancelled")
            else:
                logger.warning(f"Failed to cancel order {order.order_id}")


    async def process_fill_confirmation(self, order_id: str, price: Decimal, size: Decimal) -> None:
        """
        Process confirmed order fills from WebSocket.
        This is the ONLY place that should handle order replacement after fills.
        
        Args:
            order_id: The filled order ID
            price: Fill price
            size: Fill size
        """
        # Find the order in position map
        order_info = self.position_map.get_order_by_id(order_id)
        if not order_info:
            return

        unit, order_record = order_info
        order_type = order_record.order_type

        # Update order status to filled
        self.position_map.update_order_status(order_id, "filled", price)

        logger.warning(f"🎯 FILL at {unit}: {order_type.upper()} @ ${price:.2f}")

        # Handle based on order type
        if order_type == "sell":
            # A sell was filled - we need to replace it with a buy
            # Remove from trailing_stop
            if unit in self.trailing_stop:
                self.trailing_stop.remove(unit)

            # Decrement fragments
            self.fragments_invested = max(0, self.fragments_invested - 1)
            logger.warning(f"📊 Fragments: {self.fragments_invested}/4")

            # Place replacement buy at current unit + 1
            replacement_unit = self.unit_tracker.current_unit + 1

            if replacement_unit not in self.trailing_buy:
                result = await self._place_buy_order_at_unit(replacement_unit)
                if result:
                    self.trailing_buy.append(replacement_unit)
                    logger.success(f"✅ Replacement BUY at {replacement_unit}. Buys: {self.trailing_buy}")

                    # Cancel oldest buy if > 4
                    if len(self.trailing_buy) > 4:
                        oldest = self.trailing_buy.pop(0)
                        await self._cancel_orders_at_unit(oldest)

        elif order_type == "buy":
            # A buy was filled - we need to replace it with a sell
            # Remove from trailing_buy
            if unit in self.trailing_buy:
                self.trailing_buy.remove(unit)

            # Increment fragments
            self.fragments_invested = min(4, self.fragments_invested + 1)
            logger.warning(f"📊 Fragments: {self.fragments_invested}/4")

            # Place replacement sell at current unit - 1
            replacement_unit = self.unit_tracker.current_unit - 1

            if replacement_unit not in self.trailing_stop:
                result = await self._place_sell_order_at_unit(replacement_unit)
                if result:
                    self.trailing_stop.append(replacement_unit)
                    logger.success(f"✅ Replacement SELL at {replacement_unit}. Sells: {self.trailing_stop}")
                    
                    # Cancel oldest sell if > 4
                    if len(self.trailing_stop) > 4:
                        oldest = self.trailing_stop.pop(0)
                        await self._cancel_orders_at_unit(oldest)

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

        # Track last order history log time
        last_history_log = asyncio.get_event_loop().time()

        try:
            while self.state == StrategyState.RUNNING:
                await asyncio.sleep(10)  # Main loop heartbeat

                # Log order history every 60 seconds
                current_time = asyncio.get_event_loop().time()
                if current_time - last_history_log >= 60:
                    await self._log_order_history()
                    last_history_log = current_time

        except KeyboardInterrupt:
            logger.warning("Strategy interrupted by user")
        except Exception as e:
            logger.error(f"Strategy error: {e}")
        finally:
            await self.shutdown()

    async def _log_order_history(self) -> None:
        """Log order history from Hyperliquid for comparison with app logs."""
        try:
            fills = self.client.get_order_history(self.config.symbol, limit=20)

            if fills:
                logger.info("=" * 80)
                logger.info(f"HYPERLIQUID ORDER HISTORY (last {len(fills)} fills for {self.config.symbol})")
                logger.info("=" * 80)

                for fill in fills:
                    side = fill.get("side", "?")
                    px = fill.get("px", "?")
                    sz = fill.get("sz", "?")
                    time_ms = fill.get("time", "?")
                    oid = fill.get("oid", "?")
                    fee = fill.get("fee", "?")

                    logger.info(
                        f"  {side:5} | Size: {sz:10} | Price: ${px:10} | "
                        f"OID: {oid} | Fee: ${fee} | Time: {time_ms}"
                    )

                logger.info("=" * 80)
            else:
                logger.info(f"No order history found for {self.config.symbol}")

        except Exception as e:
            logger.error(f"Failed to log order history: {e}")


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

