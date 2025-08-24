import asyncio
import logging
from typing import Optional
import json
import os
import websockets
from app.services.exchange import exchange_manager
from app.api.simple import load_strategy_state, save_strategy_state, calculate_current_unit, get_scaling_amount

logger = logging.getLogger(__name__)

class StrategyMonitor:
    def __init__(self):
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.websocket_task: Optional[asyncio.Task] = None
        self.hyperliquid_ws_url = "wss://api.hyperliquid.xyz/ws"

    async def start_monitoring(self):
        """Start the automatic strategy monitoring with WebSocket"""
        if self.is_running:
            logger.warning("Strategy monitor is already running")
            return
        
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._websocket_monitor_loop())
        logger.info("Strategy monitor started with WebSocket connection")

    async def stop_monitoring(self):
        """Stop the automatic strategy monitoring"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        if self.websocket_task:
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass
        logger.info("Strategy monitor stopped")

    async def _websocket_monitor_loop(self):
        """Main monitoring loop using WebSocket for real-time price updates"""
        logger.info("WebSocket strategy monitor loop started")
        
        while self.is_running:
            try:
                # Load current strategy state
                state = load_strategy_state()
                if not state:
                    logger.info("No active strategy found, waiting...")
                    await asyncio.sleep(10)
                    continue

                # Start WebSocket connection for this symbol
                await self._connect_to_hyperliquid_websocket(state)
                
            except Exception as e:
                logger.error(f"Error in websocket monitor loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def _connect_to_hyperliquid_websocket(self, state):
        """Connect to HyperLiquid WebSocket for real-time price updates"""
        try:
            # Extract the base symbol from the CCXT format (e.g., "PURR/USDC:USDC" -> "PURR")
            base_symbol = state.symbol.split('/')[0]
            
            logger.info(f"Connecting to HyperLiquid WebSocket for {base_symbol}")
            
            async with websockets.connect(self.hyperliquid_ws_url) as websocket:
                # Subscribe to trades for this symbol
                subscribe_message = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "trades",
                        "coin": base_symbol
                    }
                }
                
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to trades for {base_symbol}")
                
                async for message in websocket:
                    if not self.is_running:
                        break
                        
                    try:
                        data = json.loads(message)
                        
                        # Handle trade updates
                        if data.get("channel") == "trades" and data.get("data"):
                            trades = data["data"]
                            if trades and len(trades) > 0:
                                # Get the latest trade price
                                latest_trade = trades[-1]
                                price_float = float(latest_trade.get("px", 0))
                                
                                if price_float > 0:
                                    await self._process_price_update(state, price_float)
                                    
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON from WebSocket")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        continue
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed, will retry")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}", exc_info=True)
            
    async def _process_price_update(self, state, price_float: float):
        """Process a real-time price update from WebSocket"""
        try:
            # Reload state to ensure we have the latest version
            current_state = load_strategy_state()
            if not current_state:
                return
                
            previous_unit = current_state.current_unit
            new_unit = calculate_current_unit(price_float, current_state.entry_price, current_state.unit_size)

            # Check if unit changed (only act on whole unit changes)
            if new_unit != previous_unit:
                logger.info(f"REAL-TIME UNIT CHANGE: {previous_unit} -> {new_unit} (Price: ${price_float:.2f})")
                
                # Execute the strategy logic
                await self._execute_strategy_logic(current_state, price_float, previous_unit, new_unit)
            
            # Update last price even if no action taken
            current_state.last_price = price_float
            save_strategy_state(current_state)
                
        except Exception as e:
            logger.error(f"Error processing price update: {e}", exc_info=True)

    async def _execute_strategy_logic(self, state, price_float: float, previous_unit: int, new_unit: int):
        """Execute the 4-phase strategy logic - same as in simple.py but automated"""
        try:
            orders_placed = []
            state.current_unit = new_unit
            state.last_price = price_float

            # 4-Phase Strategy Logic
            if state.phase == "ADVANCE":
                # Track peaks
                if new_unit > state.peak_unit:
                    state.peak_unit = new_unit
                    logger.info(f"NEW PEAK: Unit {state.peak_unit} at ${price_float:.2f}")
                
                # Check for decline (first drop from peak)
                elif new_unit < state.peak_unit:
                    # Transition to RETRACEMENT
                    state.phase = "RETRACEMENT"
                    
                    # Sell first 12% chunk
                    sell_amount_usd = get_scaling_amount(state, "RETRACEMENT")
                    sell_amount_tokens = sell_amount_usd / price_float
                    
                    if sell_amount_tokens > 0:
                        formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, sell_amount_tokens)
                        
                        # Calculate slippage price for sell order
                        slippage_price = price_float * 0.95  # 5% slippage for sell
                        formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                        
                        order = await exchange_manager.exchange.create_order(
                            symbol=state.symbol,
                            type="market",
                            side="sell",
                            amount=float(formatted_amount),
                            price=float(formatted_price),
                            params={}
                        )
                        
                        # Update state
                        state.long_invested -= sell_amount_usd
                        state.long_cash += sell_amount_usd
                        
                        orders_placed.append({"type": "sell", "amount": sell_amount_usd, "order_id": order.get("id")})
                        logger.info(f"RETRACEMENT STARTED: Sold ${sell_amount_usd:.2f} at unit {new_unit} (Order: {order.get('id')})")

            elif state.phase == "RETRACEMENT":
                # Continue scaling down on further declines
                if new_unit < previous_unit:
                    portion_amount = get_scaling_amount(state, "RETRACEMENT")  # 12% of total portfolio
                    
                    # Check if we have long positions left to sell
                    if state.long_invested > portion_amount:
                        # Sell the portion from long position
                        sell_amount_tokens = portion_amount / price_float
                        formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, sell_amount_tokens)
                        
                        # Calculate slippage price for sell order
                        slippage_price = price_float * 0.95  # 5% slippage for sell
                        formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                        
                        order = await exchange_manager.exchange.create_order(
                            symbol=state.symbol,
                            type="market",
                            side="sell", 
                            amount=float(formatted_amount),
                            price=float(formatted_price),
                            params={}
                        )
                        
                        state.long_invested -= portion_amount
                        
                        # ALTERNATING PATTERN: Odd units = SHORT, Even units = CASH
                        unit_distance = abs(new_unit - state.peak_unit)  # Distance from peak
                        
                        if unit_distance % 2 == 1:  # Odd units (-1, -3, -5, etc.) = SHORT
                            # Open short position with the portion amount
                            short_amount_tokens = portion_amount / price_float
                            formatted_short_amount = exchange_manager.exchange.amount_to_precision(state.symbol, short_amount_tokens)
                            
                            slippage_short_price = price_float * 1.05  # Higher price for short entry
                            formatted_short_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_short_price)
                            
                            short_order = await exchange_manager.exchange.create_order(
                                symbol=state.symbol,
                                type="market",
                                side="sell",  # Open short
                                amount=float(formatted_short_amount),
                                price=float(formatted_short_price),
                                params={"reduceOnly": False}  # Allow opening short
                            )
                            
                            state.hedge_short += portion_amount
                            orders_placed.append({"type": "sell_and_short", "sell_order": order.get("id"), "short_order": short_order.get("id"), "amount": portion_amount})
                            logger.info(f"RETRACEMENT Unit {new_unit}: Sold ${portion_amount:.2f} from long + Shorted ${portion_amount:.2f}")
                            
                        else:  # Even units (-2, -4, -6, etc.) = CASH
                            state.long_cash += portion_amount
                            orders_placed.append({"type": "sell_to_cash", "amount": portion_amount, "order_id": order.get("id")})
                            logger.info(f"RETRACEMENT Unit {new_unit}: Sold ${portion_amount:.2f} to cash")

                    # Check if we should transition to DECLINE phase  
                    if state.long_invested <= 10:
                        state.phase = "DECLINE"
                        state.valley_unit = new_unit
                        logger.info(f"TRANSITIONED TO DECLINE PHASE at unit {new_unit}")
                
                # Recovery during retracement
                elif new_unit > previous_unit:
                    state.phase = "RECOVERY"
                    
                    # Calculate portion amounts for recovery (25% of defensive positions)
                    total_defensive = state.long_cash + abs(state.hedge_short)
                    recovery_portion = total_defensive * 0.25
                    
                    # Priority 1: Cover 25% of short positions first
                    if state.hedge_short > 0:
                        hedge_portion = state.hedge_short * 0.25  # 25% of current short position
                        cover_amount = min(recovery_portion, hedge_portion)
                        
                        if cover_amount > 0:
                            cover_amount_tokens = cover_amount / price_float
                            formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, cover_amount_tokens)
                            
                            slippage_price = price_float * 1.05  # Buy to cover short
                            formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                            
                            order = await exchange_manager.exchange.create_order(
                                symbol=state.symbol,
                                type="market",
                                side="buy",
                                amount=float(formatted_amount),
                                price=float(formatted_price),
                                params={}
                            )
                            
                            state.hedge_short -= cover_amount
                            recovery_portion -= cover_amount
                            orders_placed.append({"type": "cover_short", "amount": cover_amount, "order_id": order.get("id")})
                            logger.info(f"RECOVERY: Covered ${cover_amount:.2f} short position (Order: {order.get('id')})")
                    
                    # Priority 2: Deploy remaining recovery portion from cash to long
                    if recovery_portion > 0 and state.long_cash >= recovery_portion:
                        buy_amount_tokens = recovery_portion / price_float
                        formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, buy_amount_tokens)
                        
                        slippage_price = price_float * 1.05
                        formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                        
                        order = await exchange_manager.exchange.create_order(
                            symbol=state.symbol,
                            type="market",
                            side="buy",
                            amount=float(formatted_amount),
                            price=float(formatted_price),
                            params={}
                        )
                        
                        state.long_cash -= recovery_portion
                        state.long_invested += recovery_portion
                        orders_placed.append({"type": "buy_long", "amount": recovery_portion, "order_id": order.get("id")})
                        logger.info(f"RECOVERY: Bought ${recovery_portion:.2f} long position (Order: {order.get('id')})")

            elif state.phase == "DECLINE":
                # Track valleys
                if new_unit < (state.valley_unit or 0):
                    state.valley_unit = new_unit
                    logger.info(f"NEW VALLEY: Unit {state.valley_unit} at ${price_float:.2f}")
                
                # Check for recovery
                elif new_unit > (state.valley_unit or 0):
                    state.phase = "RECOVERY"
                    logger.info(f"RECOVERY STARTED from unit {new_unit}")

            elif state.phase == "RECOVERY":
                # Continue buying back on further recovery  
                if new_unit > previous_unit:
                    # Buy back 25% of available defensive funds (cash + shorts)
                    available_funds = state.long_cash + abs(state.hedge_short)
                    buy_amount_usd = available_funds * 0.25
                    
                    # Priority 1: Cover short positions first
                    if state.hedge_short > 0 and buy_amount_usd > 0:
                        short_to_cover = min(buy_amount_usd, state.hedge_short)
                        cover_amount_tokens = short_to_cover / price_float
                        formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, cover_amount_tokens)
                        
                        slippage_price = price_float * 1.05  # Buy to cover short
                        formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                        
                        order = await exchange_manager.exchange.create_order(
                            symbol=state.symbol,
                            type="market",
                            side="buy",
                            amount=float(formatted_amount),
                            price=float(formatted_price),
                            params={}
                        )
                        
                        state.hedge_short -= short_to_cover
                        buy_amount_usd -= short_to_cover
                        orders_placed.append({"type": "cover_short", "amount": short_to_cover, "order_id": order.get("id")})
                        logger.info(f"RECOVERY: Covered ${short_to_cover:.2f} short position at unit {new_unit}")
                    
                    # Priority 2: Buy long with remaining cash
                    if buy_amount_usd > 0 and state.long_cash > buy_amount_usd:
                        buy_amount_tokens = buy_amount_usd / price_float
                        formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, buy_amount_tokens)
                        
                        slippage_price = price_float * 1.05
                        formatted_price = exchange_manager.exchange.price_to_precision(state.symbol, slippage_price)
                        
                        order = await exchange_manager.exchange.create_order(
                            symbol=state.symbol,
                            type="market",
                            side="buy",
                            amount=float(formatted_amount),
                            price=float(formatted_price),
                            params={}
                        )
                        
                        state.long_cash -= buy_amount_usd
                        state.long_invested += buy_amount_usd
                        orders_placed.append({"type": "buy_long", "amount": buy_amount_usd, "order_id": order.get("id")})
                        logger.info(f"RECOVERY: Bought ${buy_amount_usd:.2f} long position at unit {new_unit}")
                    
                    # Check for system reset (all defensive funds back in long)
                    if state.long_cash <= 10 and abs(state.hedge_short) <= 10:
                        # Reset to ADVANCE phase
                        state.phase = "ADVANCE"
                        state.entry_price = price_float
                        state.current_unit = 0
                        state.peak_unit = 0
                        state.valley_unit = None
                        # Clean up any tiny remaining amounts
                        state.long_invested += state.long_cash + state.hedge_short
                        state.long_cash = 0
                        state.hedge_short = 0
                        logger.info(f"SYSTEM RESET: Back to ADVANCE phase at ${price_float:.2f}, total value: ${state.long_invested:.2f}")

            # Save updated state
            save_strategy_state(state)
            
            if orders_placed:
                logger.info(f"Executed {len(orders_placed)} orders for unit change {previous_unit} -> {new_unit}")

        except Exception as e:
            logger.error(f"Error executing strategy logic: {e}", exc_info=True)

# Global instance
strategy_monitor = StrategyMonitor()