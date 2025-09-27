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

            logger.success(f"Initial position established: {result.filled_size} {self.config.symbol} @ ${anchor_price:.2f}")

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
            await self._place_initial_grid()

            # Subscribe to websocket feeds
            await self._setup_websocket_subscriptions()

            self.state = StrategyState.RUNNING
            logger.success(f"Strategy initialization complete for {self.config.symbol}")
            return True

        except Exception as e:
            logger.error(f"Strategy initialization failed: {e}")
            self.state = StrategyState.STOPPED
            return False

    async def _place_initial_grid(self) -> None:
        """Place the initial 4 sell orders below current price."""
        logger.info("Placing initial grid orders...")

        # Place 4 sell orders at units -1, -2, -3, -4
        initial_units = [-1, -2, -3, -4]
        for unit in initial_units:
            price = self.unit_tracker.get_unit_price(unit)

            # Calculate sell fragment (1/4 of position)
            fragment_size = self.metrics.current_position_size / 4

            logger.debug(f"Placing sell order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}")

            result = self.client.place_stop_order(
                symbol=self.config.symbol,
                is_buy=False,  # Sell order
                size=fragment_size,
                trigger_price=price,
                reduce_only=True
            )

            if result.success:
                # Track the order
                self.trailing_stop.append(unit)
                self.position_map.add_order(unit, result.order_id, "sell", fragment_size)
                logger.debug(f"Sell order placed at unit {unit}: {result.order_id}")
            else:
                logger.error(f"Failed to place sell order at unit {unit}: {result.error_message}")
        
        # The list is currently [-1, -2, -3, -4]. We reverse it to [-4, -3, -2, -1]
        # so the oldest/furthest order (-4) is at the front of the queue (index 0)
        # for easy cancellation using pop(0).
        self.trailing_stop.reverse()
        logger.info(f"Initial grid established: {len(self.trailing_stop)} sell orders active at units {self.trailing_stop}")

    async def _setup_websocket_subscriptions(self) -> None:
        """Subscribe to websocket feeds for price updates and fills."""
        # Subscribe to price updates
        await self.websocket.subscribe_to_trades(
            symbol=self.config.symbol,
            price_callback=self._on_price_update,
            fill_callback=self._on_order_fill
        )

        # Subscribe to user fills
        wallet_address = self.client.get_user_address()
        await self.websocket.subscribe_to_user_fills(wallet_address)

        logger.info(f"Subscribed to {self.config.symbol} price feed and order fills")

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
            f"Trailing Stops: {self.trailing_stop} | Trailing Buys: {self.trailing_buy}"
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

    async def _process_unit_up(self, current_unit: int) -> None:
        """
        Process a single unit move UP. This is a TRENDING UP move.
        The logic is "place-then-cancel".

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.info(f"Processing UP to unit {current_unit}")

        # An upward move triggers the closest buy order. This is the last one
        # added to the list (LIFO behavior for fills).
        if self.trailing_buy and self.trailing_buy[-1] == current_unit:
            unit_filled = self.trailing_buy.pop()
            self.position_map.update_assumed_fill(unit_filled)
            logger.success(f"Assumed BUY fill at unit {current_unit}. Remaining buys: {self.trailing_buy}")

        # 1. Place the new stop-loss sell order first.
        # This new sell order trails the price. It's placed at the unit below the current one.
        new_sell_unit = current_unit - 1
        if new_sell_unit not in self.trailing_stop:
            await self._place_sell_order_at_unit(new_sell_unit)
            self.trailing_stop.append(new_sell_unit)
            logger.info(f"Placed new SELL at unit {new_sell_unit}. Active sells: {self.trailing_stop}")

        # 2. Check if the grid has too many orders and cancel the oldest one.
        if len(self.trailing_stop) > 4:
            # The oldest order is at the beginning of the list (FIFO for cancellation).
            oldest_unit_to_cancel = self.trailing_stop.pop(0)
            logger.warning(f"Grid > 4 sells. Cancelling oldest SELL at unit {oldest_unit_to_cancel}")
            await self._cancel_orders_at_unit(oldest_unit_to_cancel)

    async def _process_unit_down(self, current_unit: int) -> None:
        """
        Process a single unit move DOWN.
        This function handles the logic for when a stop-loss may have been hit,
        or when the price is simply trending down below the active grid.
        It always ensures a new trailing buy order is placed.

        Args:
            current_unit: The new unit level the price has moved to.
        """
        logger.info(f"Processing DOWN to unit {current_unit}")

        # A downward move triggers the closest stop-loss. This is the last one
        # added to the list (LIFO behavior for fills).
        if self.trailing_stop and self.trailing_stop[-1] == current_unit:
            unit_filled = self.trailing_stop.pop()
            self.position_map.update_assumed_fill(unit_filled)
            logger.success(f"Assumed SELL fill at unit {current_unit}. Remaining sells: {self.trailing_stop}")

        # 1. Immediately place a new stop-entry buy order.
        # This new buy order is placed at the unit above the current one.
        new_buy_unit = current_unit + 1
        if new_buy_unit not in self.trailing_buy:
            await self._place_buy_order_at_unit(new_buy_unit)
            self.trailing_buy.append(new_buy_unit)
            logger.info(f"Placed new BUY at unit {new_buy_unit}. Active buys: {self.trailing_buy}")

        # 2. Check if the grid has too many buy orders and cancel the oldest one.
        if len(self.trailing_buy) > 4:
            # The oldest buy order is at the beginning of the list (FIFO for cancellation).
            oldest_unit_to_cancel = self.trailing_buy.pop(0)
            logger.warning(f"Grid > 4 buys. Cancelling oldest BUY at unit {oldest_unit_to_cancel}")
            await self._cancel_orders_at_unit(oldest_unit_to_cancel)

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

        logger.debug(f"Placing SELL order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}")

        result = self.client.place_stop_order(
            symbol=self.config.symbol,
            is_buy=False,
            size=fragment_size,
            trigger_price=price,
            reduce_only=True
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "sell", fragment_size)
            logger.debug(f"SELL order placed at unit {unit}: {result.order_id}")
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

        logger.debug(f"Placing BUY order at unit {unit} (${price:.2f}), size: {fragment_size:.4f} {self.config.symbol}, value: ${fragment_usd:.2f}")

        result = self.client.place_stop_buy(
            symbol=self.config.symbol,
            size=fragment_size,
            trigger_price=price,
            limit_price=price,
            reduce_only=False
        )

        if result.success:
            self.position_map.add_order(unit, result.order_id, "buy", fragment_size)
            logger.debug(f"BUY order placed at unit {unit}: {result.order_id}")
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

    def _on_order_fill(self, order_id: str, price: Decimal, size: Decimal) -> None:
        """
        Handle order fill notifications.

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

        try:
            while self.state == StrategyState.RUNNING:
                await asyncio.sleep(10)  # Main loop heartbeat
                # No periodic logging

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

