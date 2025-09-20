"""
V10 Strategy Manager - Implements the simplified 4-order sliding window strategy
"""
from decimal import Decimal
from typing import Dict, Optional, List
from loguru import logger
from datetime import datetime

from .data_models import (
    OrderType, GridState, ExecutionStatus,
    PositionState, PositionConfig, OrderFillEvent
)
from .unit_tracker import UnitTracker
from .position_map import add_unit_level


class V10StrategyManager:
    """
    Manages the v10 long-biased grid trading strategy.
    Core principle: Always maintain exactly 4 active orders.
    """

    def __init__(
        self,
        exchange,
        asset: str,
        wallet_allocation: Decimal,
        leverage: int,
        unit_size_usd: Decimal,
        asset_config: Dict
    ):
        """
        Initialize the v10 strategy manager.

        Args:
            exchange: The HyperliquidSDK exchange client
            asset: The asset symbol (e.g., "SOL")
            wallet_allocation: Total USD to allocate
            leverage: Leverage multiplier
            unit_size_usd: Price movement per unit
            asset_config: Asset configuration with decimals
        """
        self.exchange = exchange
        self.asset = asset
        self.wallet_allocation = wallet_allocation
        self.leverage = leverage
        self.unit_size_usd = unit_size_usd
        self.asset_config = asset_config

        # Calculate total position size
        self.total_position_usd = wallet_allocation * Decimal(str(leverage))

        # Position tracking
        self.position_state: Optional[PositionState] = None
        self.position_map: Dict[int, PositionConfig] = {}
        self.unit_tracker: Optional[UnitTracker] = None

        # Order tracking
        self.active_orders: Dict[str, Dict] = {}  # order_id -> order details
        self.is_initialized = False

        logger.info(f"V10 Strategy initialized: {asset}, ${wallet_allocation} x {leverage}x = ${self.total_position_usd}")

    async def initialize_position(self, current_price: Decimal) -> bool:
        """
        Initialize the strategy with a market buy and place initial 4 sell orders.
        This implements the v10 strategy's initial setup.

        Args:
            current_price: Current market price

        Returns:
            True if successful, False otherwise
        """
        if self.is_initialized:
            logger.warning("Strategy already initialized")
            return False

        logger.info(f"Initializing v10 strategy at price ${current_price:.2f}")

        # Step 1: Execute market buy for full position
        asset_size = self.total_position_usd / current_price

        # Round to asset decimals
        decimals = self.asset_config.get("size_decimals", 2)
        asset_size = round(asset_size, decimals)

        logger.info(f"Placing market buy for {asset_size} {self.asset} at ~${current_price:.2f}")

        # Use limit order with IOC for market-like execution
        order_data = {
            "coin": self.asset,
            "is_buy": True,
            "sz": float(asset_size),
            "limit_px": float(current_price * Decimal("1.01")),  # 1% slippage tolerance
            "order_type": {"limit": {"tif": "Ioc"}}  # Immediate or Cancel
        }

        response = await self.exchange.place_order(order_data)

        if not response or response.get("status") != "ok":
            logger.error(f"Failed to place initial market buy: {response}")
            return False

        # Step 2: Initialize position tracking
        self.position_state = PositionState(
            entry_price=current_price,
            unit_size_usd=self.unit_size_usd,
            asset_size=asset_size,
            position_value_usd=self.total_position_usd,
            original_asset_size=asset_size,
            original_position_value_usd=self.total_position_usd,
            long_fragment_usd=Decimal("0"),
            long_fragment_asset=Decimal("0")
        )

        # Initialize position map with units -5 to +5
        for unit in range(-5, 6):
            unit_price = self.position_state.get_price_for_unit(unit)
            self.position_map[unit] = PositionConfig(unit=unit, price=unit_price)

        # Step 3: Initialize unit tracker
        self.unit_tracker = UnitTracker(self.position_state, self.position_map)

        # Step 4: Place initial 4 stop-loss sell orders
        await self._place_initial_grid()

        self.is_initialized = True
        logger.success(f"V10 strategy initialized successfully with 4 sell orders")
        return True

    async def _place_initial_grid(self):
        """
        Place the initial 4 stop-loss sell orders at units -1, -2, -3, -4.
        """
        # Each order is 25% of position (fragment)
        fragment_size = self.position_state.long_fragment_asset

        for unit in [-1, -2, -3, -4]:
            trigger_price = self.position_state.get_price_for_unit(unit)

            # Place stop-loss sell order using trigger format
            order_data = {
                "coin": self.asset,
                "is_buy": False,
                "sz": float(fragment_size),
                "limit_px": float(trigger_price * Decimal("0.99")),  # Limit price slightly below trigger
                "order_type": {
                    "trigger": {
                        "triggerPx": float(trigger_price),
                        "isMarket": True,
                        "tpsl": "sl"  # Stop-loss
                    }
                }
            }

            response = await self.exchange.place_order(order_data)

            if response and response.get("status") == "ok":
                order_id = response["response"]["data"]["statuses"][0]["resting"]["oid"]

                # Track order
                self.active_orders[order_id] = {
                    "unit": unit,
                    "type": OrderType.STOP_LOSS_SELL,
                    "size": fragment_size,
                    "trigger_price": trigger_price
                }

                # Update position map
                self.position_map[unit].set_active_order(order_id, OrderType.STOP_LOSS_SELL)

                logger.info(f"Placed stop-loss sell at unit {unit} (${trigger_price:.2f})")
            else:
                logger.error(f"Failed to place stop-loss at unit {unit}: {response}")

    async def handle_order_fill(self, order_id: str, filled_price: Decimal, filled_size: Decimal):
        """
        Handle an order fill event and immediately place replacement order.
        This is the core v10 logic: always maintain 4 orders.

        Args:
            order_id: The filled order ID
            filled_price: Execution price
            filled_size: Filled size
        """
        if order_id not in self.active_orders:
            logger.warning(f"Unknown order filled: {order_id}")
            return

        order_info = self.active_orders[order_id]
        filled_unit = order_info["unit"]
        order_type = order_info["type"]

        logger.success(f"Order filled: {order_type.value} at unit {filled_unit}, price ${filled_price:.2f}")

        # Update position map
        self.position_map[filled_unit].mark_filled(filled_price, filled_size)

        # Remove from active orders
        del self.active_orders[order_id]

        # Update unit tracker lists
        if order_type == OrderType.STOP_LOSS_SELL:
            self.unit_tracker.remove_trailing_stop(filled_unit)
            # Place replacement buy order at current_unit + 1
            replacement_unit = self.unit_tracker.current_unit + 1
            self.unit_tracker.add_trailing_buy(replacement_unit)
            await self._place_stop_buy(replacement_unit)

        elif order_type == OrderType.STOP_BUY:
            self.unit_tracker.remove_trailing_buy(filled_unit)
            # Place replacement sell order at current_unit - 1
            replacement_unit = self.unit_tracker.current_unit - 1
            self.unit_tracker.add_trailing_stop(replacement_unit)
            await self._place_stop_sell(replacement_unit)

        # Log current grid state
        state = self.unit_tracker.get_window_state()
        logger.info(f"Grid state after fill: {state['grid_state']}, Orders: {state['window_composition']}")

    async def _place_stop_sell(self, unit: int):
        """
        Place a stop-loss sell order at the specified unit.

        Args:
            unit: The unit level for the order
        """
        trigger_price = self.position_state.get_price_for_unit(unit)
        fragment_size = self.position_state.long_fragment_asset

        order_data = {
            "coin": self.asset,
            "is_buy": False,
            "sz": float(fragment_size),
            "limit_px": float(trigger_price * Decimal("0.99")),
            "order_type": {
                "trigger": {
                    "triggerPx": float(trigger_price),
                    "isMarket": True,
                    "tpsl": "sl"
                }
            }
        }

        response = await self.exchange.place_order(order_data)

        if response and response.get("status") == "ok":
            order_id = response["response"]["data"]["statuses"][0]["resting"]["oid"]

            self.active_orders[order_id] = {
                "unit": unit,
                "type": OrderType.STOP_LOSS_SELL,
                "size": fragment_size,
                "trigger_price": trigger_price
            }

            self.position_map[unit].set_active_order(order_id, OrderType.STOP_LOSS_SELL)
            logger.info(f"Placed stop-loss sell at unit {unit} (${trigger_price:.2f})")
        else:
            logger.error(f"Failed to place stop-loss at unit {unit}: {response}")

    async def _place_stop_buy(self, unit: int):
        """
        Place a stop-entry buy order at the specified unit.

        Args:
            unit: The unit level for the order
        """
        trigger_price = self.position_state.get_price_for_unit(unit)

        # Get adjusted fragment size (includes reinvested PnL)
        fragment_usd = self.unit_tracker.get_adjusted_fragment_usd()
        asset_size = fragment_usd / trigger_price

        # Round to asset decimals
        decimals = self.asset_config.get("size_decimals", 2)
        asset_size = round(asset_size, decimals)

        # Note: Hyperliquid uses stop-loss orders for both directions
        # A stop-loss buy triggers when price goes UP to the trigger price
        order_data = {
            "coin": self.asset,
            "is_buy": True,
            "sz": float(asset_size),
            "limit_px": float(trigger_price * Decimal("1.01")),  # Limit above trigger for buys
            "order_type": {
                "trigger": {
                    "triggerPx": float(trigger_price),
                    "isMarket": True,
                    "tpsl": "tp"  # Take-profit acts as stop-entry for buys
                }
            }
        }

        response = await self.exchange.place_order(order_data)

        if response and response.get("status") == "ok":
            order_id = response["response"]["data"]["statuses"][0]["resting"]["oid"]

            self.active_orders[order_id] = {
                "unit": unit,
                "type": OrderType.STOP_BUY,
                "size": asset_size,
                "trigger_price": trigger_price
            }

            self.position_map[unit].set_active_order(order_id, OrderType.STOP_BUY)
            logger.info(f"Placed stop-entry buy at unit {unit} (${trigger_price:.2f})")
        else:
            logger.error(f"Failed to place stop-buy at unit {unit}: {response}")

    async def update_grid_sliding(self, current_price: Decimal):
        """
        Implement grid sliding for trending markets.
        When price moves without triggering orders, slide the grid to follow.

        Args:
            current_price: Current market price
        """
        if not self.is_initialized:
            return

        # Calculate unit change
        unit_event = self.unit_tracker.calculate_unit_change(current_price)

        if not unit_event:
            return  # No unit change

        logger.info(f"Unit changed: {unit_event.direction} to unit {unit_event.current_unit}")

        # Get current grid state
        grid_state = self.unit_tracker.get_grid_state()

        # Grid sliding logic based on state
        if grid_state == GridState.FULL_POSITION:
            # All sells, slide up if price advancing
            await self._slide_sell_grid()

        elif grid_state == GridState.FULL_CASH:
            # All buys, slide down if price declining
            await self._slide_buy_grid()

        # Mixed state doesn't need sliding, orders will trigger naturally

    async def _slide_sell_grid(self):
        """
        Slide the sell grid up when in full position and price advancing.
        Add new sell at current_unit - 1, remove furthest sell.
        """
        current_unit = self.unit_tracker.current_unit

        # Check if we need to slide (furthest order is too far)
        furthest_stop = min(self.unit_tracker.trailing_stop)

        if current_unit - furthest_stop > 4:
            # Remove furthest stop order
            await self._cancel_order_at_unit(furthest_stop)
            self.unit_tracker.remove_trailing_stop(furthest_stop)

            # Add new stop closer to current price
            new_unit = current_unit - 1
            if new_unit not in self.unit_tracker.trailing_stop:
                self.unit_tracker.add_trailing_stop(new_unit)
                await self._place_stop_sell(new_unit)

                logger.info(f"Slid sell grid: removed unit {furthest_stop}, added unit {new_unit}")

    async def _slide_buy_grid(self):
        """
        Slide the buy grid down when in full cash and price declining.
        Add new buy at current_unit + 1, remove furthest buy.
        """
        current_unit = self.unit_tracker.current_unit

        # Check if we need to slide (furthest order is too far)
        furthest_buy = max(self.unit_tracker.trailing_buy)

        if furthest_buy - current_unit > 4:
            # Remove furthest buy order
            await self._cancel_order_at_unit(furthest_buy)
            self.unit_tracker.remove_trailing_buy(furthest_buy)

            # Add new buy closer to current price
            new_unit = current_unit + 1
            if new_unit not in self.unit_tracker.trailing_buy:
                self.unit_tracker.add_trailing_buy(new_unit)
                await self._place_stop_buy(new_unit)

                logger.info(f"Slid buy grid: removed unit {furthest_buy}, added unit {new_unit}")

    async def _cancel_order_at_unit(self, unit: int):
        """
        Cancel the order at a specific unit level.

        Args:
            unit: The unit level
        """
        # Find order ID for this unit
        for order_id, info in self.active_orders.items():
            if info["unit"] == unit:
                # Cancel via exchange
                response = await self.exchange.cancel_order(self.asset, order_id)
                if response and response.get("status") == "ok":
                    logger.debug(f"Cancelled order at unit {unit}")
                    del self.active_orders[order_id]
                    self.position_map[unit].mark_cancelled()
                break

    def get_status(self) -> Dict:
        """
        Get current strategy status for monitoring.

        Returns:
            Dictionary with strategy status
        """
        if not self.is_initialized:
            return {"status": "not_initialized"}

        window_state = self.unit_tracker.get_window_state()

        return {
            "status": "running",
            "asset": self.asset,
            "current_unit": window_state["current_unit"],
            "grid_state": window_state["grid_state"],
            "order_composition": window_state["window_composition"],
            "active_orders": len(self.active_orders),
            "realized_pnl": window_state["current_realized_pnl"],
            "position_value": float(self.total_position_usd)
        }