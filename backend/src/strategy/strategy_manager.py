"""
Strategy Manager - CORRECTED VERSION with proper leverage/margin calculations
Coordinates WebSocket price tracking with exchange operations
"""
import asyncio
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.models import UnitTracker, Phase
from ..core.websocket_client import HyperliquidWebSocketClient
from ..exchange.exchange_client import HyperliquidExchangeClient
from ..utils.config import settings
from ..utils.trade_logger import TradeLogger
from ..utils.notifications import NotificationManager
from ..utils.state_persistence import StatePersistence
from .short_position import ShortPosition


class StrategyState:
    """CORRECTED: Holds complete state with proper short position tracking"""
    
    def __init__(self, symbol: str, position_size_usd: Decimal, unit_size: Decimal, leverage: int = 25):
        # Configuration
        self.symbol = symbol
        self.position_size_usd = position_size_usd
        self.unit_size = unit_size
        self.leverage = leverage  # ETH is 25x on Hyperliquid
        
        # CORRECTED: Track notional vs margin separately
        self.notional_allocation = position_size_usd  # Total position value ($1000)
        self.margin_allocation = position_size_usd / Decimal(leverage)  # Margin required ($40 at 25x)
        self.initial_notional_allocation = position_size_usd
        self.initial_margin_allocation = position_size_usd / Decimal(leverage)
        
        # CORRECTED: Fragment calculations - 12% of notional, not 10%
        self.position_fragment_usd = Decimal("0")  # 12% of notional value
        self.position_fragment_eth = Decimal("0")  # ETH amount locked at peak
        
        # CORRECTED: Track individual short positions for accurate P&L
        self.short_positions: List[ShortPosition] = []
        
        # RESET tracking
        self.reset_count = 0
        self.pre_reset_notional = position_size_usd
        self.pre_reset_margin = position_size_usd / Decimal(leverage)
        
        # Recovery tracking
        self.last_recovery_unit = 0
        
        # Entry tracking
        self.entry_price: Optional[Decimal] = None
        self.entry_time: Optional[datetime] = None
        self.has_position = False
        
        # Peak tracking
        self.peak_price: Optional[Decimal] = None
        
        # Unit tracker
        self.unit_tracker = UnitTracker(unit_size=unit_size)
    
    def calculate_position_fragment_at_peak(self, peak_price: Decimal):
        """CORRECTED: Calculate 12% fragment at peak and LOCK IT"""
        # Update notional allocation based on current ETH holdings at peak price
        # (This accounts for any growth during ADVANCE phase)
        current_eth_amount = self.notional_allocation / peak_price  # Approximate
        self.notional_allocation = current_eth_amount * peak_price
        
        # Calculate 12% fragment (better for 8-step scaling)
        self.position_fragment_usd = self.notional_allocation * Decimal("0.12")
        self.position_fragment_eth = self.position_fragment_usd / peak_price
        self.peak_price = peak_price
        
        logger.info(f"🔒 FRAGMENT LOCKED AT PEAK ${peak_price}:")
        logger.info(f"  Notional Value: ${self.notional_allocation}")
        logger.info(f"  Fragment USD: ${self.position_fragment_usd}")
        logger.info(f"  Fragment ETH: {self.position_fragment_eth:.6f} ETH")
        logger.info(f"  This ETH amount stays CONSTANT during retracement")
        
        return self.position_fragment_usd
    
    def add_short_position(self, usd_amount: Decimal, entry_price: Decimal, unit_level: int):
        """Add a new short position to tracking"""
        eth_amount = usd_amount / entry_price
        short = ShortPosition(
            usd_amount=usd_amount,
            entry_price=entry_price,
            eth_amount=eth_amount,
            unit_opened=unit_level
        )
        self.short_positions.append(short)
        
        logger.info(f"📝 Added short position:")
        logger.info(f"  USD: ${usd_amount}")
        logger.info(f"  Entry: ${entry_price}")
        logger.info(f"  ETH: {eth_amount:.6f}")
        logger.info(f"  Unit: {unit_level}")
    
    def calculate_total_short_value(self, current_price: Decimal) -> Decimal:
        """CORRECTED: Calculate total short value including unrealized P&L"""
        total_value = Decimal("0")
        total_pnl = Decimal("0")
        
        logger.info(f"SHORT POSITION VALUATION at ${current_price}:")
        
        for i, short in enumerate(self.short_positions, 1):
            current_value = short.get_current_value(current_price)
            pnl = short.get_pnl(current_price)
            total_value += current_value
            total_pnl += pnl
            
            logger.info(f"  Short #{i}: {short.eth_amount:.6f} ETH @ ${short.entry_price}")
            logger.info(f"    Original: ${short.usd_amount} → Current: ${current_value:.2f} (P&L: ${pnl:.2f})")
        
        logger.info(f"  📊 TOTAL SHORT VALUE: ${total_value:.2f}")
        logger.info(f"  📊 TOTAL SHORT P&L: ${total_pnl:.2f}")
        
        return total_value
    
    def calculate_hedge_fragment(self, current_price: Decimal) -> Decimal:
        """CORRECTED: Calculate 25% of CURRENT short value (including P&L)"""
        total_short_value = self.calculate_total_short_value(current_price)
        hedge_fragment = total_short_value * Decimal("0.25")
        
        logger.info(f"HEDGE FRAGMENT CALCULATION:")
        logger.info(f"  Total Short Value: ${total_short_value:.2f}")
        logger.info(f"  Hedge Fragment (25%): ${hedge_fragment:.2f}")
        logger.info(f"  Position Fragment (cash): ${self.position_fragment_usd}")
        logger.info(f"  🎯 Total Recovery Purchase: ${hedge_fragment + self.position_fragment_usd:.2f}")
        
        return hedge_fragment
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for persistence"""
        return {
            "symbol": self.symbol,
            "phase": self.unit_tracker.phase.value if self.unit_tracker.phase else "UNKNOWN",
            "position_size_usd": self.position_size_usd,
            "unit_size": self.unit_size,
            "leverage": self.leverage,
            "notional_allocation": self.notional_allocation,
            "margin_allocation": self.margin_allocation,
            "initial_notional_allocation": self.initial_notional_allocation,
            "initial_margin_allocation": self.initial_margin_allocation,
            "position_fragment_usd": self.position_fragment_usd,
            "position_fragment_eth": self.position_fragment_eth,
            "short_positions": [short.to_dict() for short in self.short_positions],
            "reset_count": self.reset_count,
            "pre_reset_notional": self.pre_reset_notional,
            "pre_reset_margin": self.pre_reset_margin,
            "last_recovery_unit": self.last_recovery_unit,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "has_position": self.has_position,
            "peak_price": self.peak_price,
            "current_unit": self.unit_tracker.current_unit,
            "peak_unit": self.unit_tracker.peak_unit,
            "valley_unit": self.unit_tracker.valley_unit,
        }


class StrategyManager:
    """CORRECTED Strategy Manager with proper leverage/margin handling"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.ws_client = HyperliquidWebSocketClient(testnet=testnet)
        self.exchange_client = HyperliquidExchangeClient(testnet=testnet)
        self.strategies: Dict[str, StrategyState] = {}
        self.is_running = False
        self.trade_logger = TradeLogger()
        self.notifier = NotificationManager()
        self.state_persistence = StatePersistence()
    
    def save_state(self, symbol: str):
        """Save current strategy state to disk"""
        if symbol in self.strategies:
            state = self.strategies[symbol]
            self.state_persistence.save_state(symbol, state.to_dict())
    
    async def start_strategy(
        self,
        symbol: str,
        position_size_usd: Decimal,
        unit_size: Decimal,
        leverage: int = 25  # ETH is 25x on Hyperliquid
    ) -> bool:
        """Start a trading strategy - CORRECTED with proper leverage"""
        try:
            logger.info("=" * 60)
            logger.info(f"HYPERTRADER - CORRECTED LEVERAGE CALCULATIONS")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Notional Position: ${position_size_usd}")
            logger.info(f"Margin Required: ${position_size_usd / Decimal(leverage)} (at {leverage}x)")
            logger.info(f"Unit Size: ${unit_size}")
            logger.info("=" * 60)
            
            # Check if strategy already exists
            if symbol in self.strategies:
                logger.warning(f"Strategy already running for {symbol}")
                return False
            
            # Create strategy state
            state = StrategyState(symbol, position_size_usd, unit_size, leverage)
            self.strategies[symbol] = state
            
            # Check existing position
            existing_position = self.exchange_client.get_position(symbol)
            if existing_position:
                logger.warning(f"Existing position found for {symbol}")
                logger.info(f"Position: {existing_position['side']} {existing_position.get('contracts', 'N/A')}")
                logger.info("Please close existing position before starting new strategy")
                return False
            
            # Enter trade (100% long position) - Use notional amount
            logger.info("\nPhase: ENTERING TRADE")
            logger.info("Opening 100% long position...")
            
            # CORRECTED: Use buy_long_usd method for USD-based entry
            order = await self.exchange_client.buy_long_usd(
                symbol=symbol,
                usd_amount=position_size_usd,
                leverage=leverage
            )
            
            if order:
                # Update state
                state.has_position = True
                state.entry_time = datetime.now()
                
                # Get entry price from order or current market
                if order.get("price") and order["price"] != 0:
                    state.entry_price = Decimal(str(order["price"]))
                else:
                    state.entry_price = self.exchange_client.get_current_price(symbol)
                
                # Set entry price in unit tracker
                state.unit_tracker.entry_price = state.entry_price
                
                # Set phase to ADVANCE
                state.unit_tracker.phase = Phase.ADVANCE
                
                logger.success(f"Position opened successfully")
                logger.info(f"Entry Price: ${state.entry_price:.2f}")
                logger.info(f"Notional Value: ${state.notional_allocation}")
                logger.info(f"Margin Used: ${state.margin_allocation}")
                logger.info(f"Phase: ADVANCE")
                
                # Save state after successful entry
                self.save_state(symbol)
                
                # Start WebSocket monitoring
                await self._start_monitoring(symbol, unit_size)
                
                return True
            else:
                logger.error("Failed to open position")
                del self.strategies[symbol]
                return False
                
        except Exception as e:
            logger.error(f"Error starting strategy: {e}")
            if symbol in self.strategies:
                del self.strategies[symbol]
            return False
    
    async def handle_advance_phase(self, symbol: str):
        """CORRECTED ADVANCE phase with proper fragment locking"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        # Get current position
        position = self.exchange_client.get_position(symbol)
        if position:
            current_price = self.exchange_client.get_current_price(symbol)
            
            # CORRECTED: Only recalculate fragment on NEW PEAKS
            if state.unit_tracker.current_unit > state.unit_tracker.peak_unit:
                # NEW PEAK - recalculate and LOCK fragment
                state.calculate_position_fragment_at_peak(current_price)
                
                logger.success(f"📈 NEW PEAK REACHED:")
                logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
                logger.info(f"  🔒 Fragment LOCKED: ${state.position_fragment_usd} = {state.position_fragment_eth:.6f} ETH")
            else:
                # NOT a new peak - keep existing fragment
                logger.info(f"ADVANCE Phase Update:")
                logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
                logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
                logger.info(f"  🔒 USING Locked Fragment: ${state.position_fragment_usd} = {state.position_fragment_eth:.6f} ETH")
            
            # Check for phase transition to RETRACEMENT
            units_from_peak = state.unit_tracker.get_units_from_peak()
            if units_from_peak <= -1:
                logger.warning(f"💥 Price dropped {abs(units_from_peak)} unit(s) from peak")
                logger.warning(f"🔒 Fragment LOCKED: {state.position_fragment_eth:.6f} ETH")
                logger.info("Transitioning to RETRACEMENT phase")
                state.unit_tracker.phase = Phase.RETRACEMENT
                await self.handle_retracement_phase(symbol)
    
    async def handle_retracement_phase(self, symbol: str):
        """CORRECTED RETRACEMENT phase with USD buy, ETH sell pattern"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        units_from_peak = state.unit_tracker.get_units_from_peak()
        current_price = self.exchange_client.get_current_price(symbol)
        
        logger.info("=" * 60)
        logger.info(f"RETRACEMENT Phase - {abs(units_from_peak)} units from peak")
        logger.info(f"Current Price: ${current_price}")
        logger.info(f"Fragment ETH (constant): {state.position_fragment_eth:.6f} ETH")
        logger.info(f"Fragment USD (original): ${state.position_fragment_usd}")
        logger.info("=" * 60)
        
        try:
            if units_from_peak in [-1, -2, -3, -4]:
                # CORRECTED: Execute retracement action
                logger.info(f"Action: Sell {state.position_fragment_eth:.6f} ETH, Short ${state.position_fragment_usd}")
                
                # Step 1: Sell ETH amount (constant from peak)
                sell_result = await self.exchange_client.sell_long_eth(
                    symbol=symbol,
                    eth_amount=state.position_fragment_eth,
                    reduce_only=True
                )
                
                if sell_result:
                    logger.success(f"✅ Reduced long by {state.position_fragment_eth:.6f} ETH")
                    logger.success(f"   Received: ${sell_result.get('usd_received', 0):.2f}")
                
                # Step 2: Open short with USD amount (constant from peak)
                short_result = await self.exchange_client.open_short_usd(
                    symbol=symbol,
                    usd_amount=state.position_fragment_usd,
                    leverage=state.leverage
                )
                
                if short_result:
                    logger.success(f"✅ Opened short: ${state.position_fragment_usd}")
                    
                    # Track the short position
                    state.add_short_position(
                        usd_amount=state.position_fragment_usd,
                        entry_price=current_price,
                        unit_level=units_from_peak
                    )
                
                # Log portfolio approximation
                short_count = len(state.short_positions)
                remaining_long_pct = max(0, 100 - (short_count * 12))
                short_pct = short_count * 12
                
                logger.info(f"Portfolio (approx): {remaining_long_pct}% Long / {short_pct}% Short")
                
            elif units_from_peak <= -5:
                # Enter DECLINE phase
                logger.info("Price dropped -5+ units - Entering DECLINE phase")
                state.unit_tracker.phase = Phase.DECLINE
                state.unit_tracker.valley_unit = state.unit_tracker.current_unit
                await self.handle_decline_phase(symbol)
                
        except Exception as e:
            logger.error(f"Error in RETRACEMENT phase: {e}")
    
    async def handle_decline_phase(self, symbol: str):
        """CORRECTED DECLINE phase - track valley and short value growth"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        current_price = self.exchange_client.get_current_price(symbol)
        
        # Update valley if we've made a new low
        if state.unit_tracker.current_unit < state.unit_tracker.valley_unit:
            state.unit_tracker.valley_unit = state.unit_tracker.current_unit
            logger.info(f"📉 NEW VALLEY: Unit {state.unit_tracker.valley_unit}")
        
        # Calculate current short position value (including P&L gains)
        if state.short_positions:
            total_short_value = state.calculate_total_short_value(current_price)
            
            logger.info("=" * 60)
            logger.info("DECLINE Phase Status")
            logger.info("=" * 60)
            logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
            logger.info(f"  Valley Unit: {state.unit_tracker.valley_unit}")
            logger.info(f"  Short Positions: {len(state.short_positions)}")
            logger.info(f"  🚀 Total Short Value: ${total_short_value:.2f}")
            logger.info(f"  Growth from shorts: ${total_short_value - (len(state.short_positions) * state.position_fragment_usd):.2f}")
        
        # Check for phase transition to RECOVERY
        units_from_valley = state.unit_tracker.get_units_from_valley()
        if units_from_valley >= 2:
            logger.info(f"Price recovered {units_from_valley} units from valley")
            logger.info("Transitioning to RECOVERY phase")
            state.unit_tracker.phase = Phase.RECOVERY
            await self.handle_recovery_phase(symbol)
    
    async def handle_recovery_phase(self, symbol: str):
        """CORRECTED RECOVERY phase with proper hedge fragment calculation"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        units_from_valley = state.unit_tracker.get_units_from_valley()
        current_price = self.exchange_client.get_current_price(symbol)
        
        # Check if we've already processed this recovery level
        if units_from_valley <= state.last_recovery_unit:
            logger.debug(f"Already processed recovery unit {units_from_valley}")
            return
        
        # Update last processed unit
        state.last_recovery_unit = units_from_valley
        
        logger.info("=" * 60)
        logger.info(f"RECOVERY Phase - {units_from_valley} units from valley")
        logger.info(f"Current Price: ${current_price}")
        logger.info("=" * 60)
        
        try:
            if units_from_valley >= 2 and units_from_valley <= 5:
                # CORRECTED: Calculate hedge fragment from current short value
                hedge_fragment_usd = state.calculate_hedge_fragment(current_price)
                
                # Close short: Whatever ETH amount the hedge fragment represents
                hedge_eth_to_close = hedge_fragment_usd / current_price
                
                # Buy long: Hedge proceeds + position fragment
                total_long_purchase = hedge_fragment_usd + state.position_fragment_usd
                
                logger.info(f"Action: Close {hedge_eth_to_close:.6f} ETH short, Buy ${total_long_purchase:.2f} long")
                
                # Execute trades
                close_result = await self.exchange_client.close_short_eth(
                    symbol=symbol,
                    eth_amount=hedge_eth_to_close
                )
                
                if close_result:
                    logger.success(f"✅ Closed {hedge_eth_to_close:.6f} ETH short")
                
                buy_result = await self.exchange_client.buy_long_usd(
                    symbol=symbol,
                    usd_amount=total_long_purchase,
                    leverage=state.leverage
                )
                
                if buy_result:
                    logger.success(f"✅ Bought ${total_long_purchase:.2f} long")
                    logger.info(f"  - From short proceeds: ${hedge_fragment_usd:.2f}")
                    logger.info(f"  - From cash: ${state.position_fragment_usd}")
                
            elif units_from_valley >= 6:
                # Final recovery - close all shorts, trigger reset
                logger.info("Final recovery unit - closing all remaining shorts")
                
                # Close all remaining short positions
                total_remaining_short_value = state.calculate_total_short_value(current_price)
                remaining_eth_to_close = total_remaining_short_value / current_price
                
                close_result = await self.exchange_client.close_short_eth(
                    symbol=symbol,
                    eth_amount=remaining_eth_to_close
                )
                
                if close_result:
                    logger.success(f"✅ Closed all remaining shorts")
                
                # Buy final long position
                final_purchase = total_remaining_short_value + state.position_fragment_usd
                buy_result = await self.exchange_client.buy_long_usd(
                    symbol=symbol,
                    usd_amount=final_purchase,
                    leverage=state.leverage
                )
                
                if buy_result:
                    logger.success(f"✅ Final long purchase: ${final_purchase:.2f}")
                
                # Trigger RESET mechanism
                logger.info("Position now 100% long - Triggering RESET")
                await self.handle_reset_mechanism(symbol)
                
        except Exception as e:
            logger.error(f"Error in RECOVERY phase: {e}")
    
    async def handle_reset_mechanism(self, symbol: str):
        """CORRECTED RESET mechanism with compound growth tracking"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        logger.info("=" * 60)
        logger.info("🔄 RESET MECHANISM TRIGGERED")
        logger.info("=" * 60)
        
        try:
            # Get current position value
            position = self.exchange_client.get_position(symbol)
            if not position:
                logger.error("No position found for reset")
                return
            
            current_price = self.exchange_client.get_current_price(symbol)
            current_notional_value = abs(position.get("contracts", 0)) * current_price
            current_margin_value = current_notional_value / Decimal(state.leverage)
            
            # Calculate compound growth
            cycle_growth = current_notional_value - state.notional_allocation
            growth_percentage = (cycle_growth / state.notional_allocation) * 100
            
            logger.info(f"Cycle Summary:")
            logger.info(f"  Starting Notional: ${state.notional_allocation:.2f}")
            logger.info(f"  Ending Notional: ${current_notional_value:.2f}")
            logger.info(f"  🚀 Compound Growth: ${cycle_growth:.2f} ({growth_percentage:.2f}%)")
            logger.info(f"  Reset #{state.reset_count + 1}")
            
            # Store pre-reset values
            state.pre_reset_notional = state.notional_allocation
            state.pre_reset_margin = state.margin_allocation
            
            # RESET: Update allocations to current values (compound the growth)
            state.notional_allocation = current_notional_value
            state.margin_allocation = current_margin_value
            state.initial_notional_allocation = current_notional_value
            state.initial_margin_allocation = current_margin_value
            
            # Clear short positions
            state.short_positions.clear()
            
            # RESET unit tracking variables
            state.unit_tracker.current_unit = 0
            state.unit_tracker.peak_unit = 0
            state.unit_tracker.valley_unit = 0
            
            # Update entry price and reset fragment values
            state.entry_price = current_price
            state.unit_tracker.entry_price = current_price
            state.position_fragment_usd = Decimal("0")
            state.position_fragment_eth = Decimal("0")
            state.peak_price = None
            
            # Set phase to ADVANCE
            state.unit_tracker.phase = Phase.ADVANCE
            state.reset_count += 1
            state.last_recovery_unit = 0
            
            logger.success("🔄 RESET Complete!")
            logger.info(f"New Baseline:")
            logger.info(f"  Notional Value: ${state.notional_allocation:.2f}")
            logger.info(f"  Margin Value: ${state.margin_allocation:.2f}")
            logger.info(f"  Entry Price: ${state.entry_price:.2f}")
            logger.info(f"  Phase: {state.unit_tracker.phase.value}")
            logger.info(f"  Total Resets: {state.reset_count}")
            logger.info("")
            logger.info("🚀 Strategy re-calibrated with compounded gains!")
            logger.info("Entering ADVANCE phase with larger position size")
            
        except Exception as e:
            logger.error(f"Error in RESET mechanism: {e}")
    
    async def monitor_price_change(self, symbol: str, new_price: Decimal):
        """Monitor price changes and trigger appropriate phase handlers"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        previous_unit = state.unit_tracker.current_unit
        
        # Update unit tracker with new price
        unit_changed = state.unit_tracker.calculate_unit_change(new_price)
        
        if not unit_changed:
            return
        
        logger.info(f"Unit changed: {previous_unit} -> {state.unit_tracker.current_unit}")
        
        # Handle based on current phase
        if state.unit_tracker.phase == Phase.ADVANCE:
            await self.handle_advance_phase(symbol)
        elif state.unit_tracker.phase == Phase.RETRACEMENT:
            await self.handle_retracement_phase(symbol)
        elif state.unit_tracker.phase == Phase.DECLINE:
            await self.handle_decline_phase(symbol)
        elif state.unit_tracker.phase == Phase.RECOVERY:
            await self.handle_recovery_phase(symbol)
    
    async def _start_monitoring(self, symbol: str, unit_size: Decimal):
        """Start WebSocket monitoring for price changes"""
        try:
            # Connect WebSocket if not connected
            if not self.ws_client.is_connected:
                await self.ws_client.connect()
            
            # Get the strategy state
            state = self.strategies[symbol]
            
            # Create callback for price changes
            async def price_change_callback(new_price: Decimal):
                await self.monitor_price_change(symbol, new_price)
            
            # Subscribe using strategy's unit tracker and callback
            coin = symbol.split("/")[0]  # Extract coin from symbol
            await self.ws_client.subscribe_to_trades(
                coin, 
                unit_size,
                unit_tracker=state.unit_tracker,
                price_callback=price_change_callback
            )
            
            logger.info(f"Started monitoring {coin} prices with corrected strategy")
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
    
    async def get_strategy_status(self, symbol: str) -> Dict[str, Any]:
        """CORRECTED status reporting with notional/margin details and compound tracking"""
        if symbol not in self.strategies:
            return {"error": f"No strategy found for {symbol}"}
        
        state = self.strategies[symbol]
        
        # Get current position from exchange
        position = self.exchange_client.get_position(symbol)
        current_price = self.exchange_client.get_current_price(symbol)
        
        # Calculate current short value if any shorts exist
        total_short_value = Decimal("0")
        if state.short_positions:
            total_short_value = state.calculate_total_short_value(current_price)
        
        return {
            "symbol": symbol,
            "phase": state.unit_tracker.phase.value,
            "entry_price": float(state.entry_price) if state.entry_price else None,
            "current_price": float(current_price),
            "leverage": state.leverage,
            "current_unit": state.unit_tracker.current_unit,
            "peak_unit": state.unit_tracker.peak_unit,
            "valley_unit": state.unit_tracker.valley_unit,
            "units_from_peak": state.unit_tracker.get_units_from_peak(),
            "units_from_valley": state.unit_tracker.get_units_from_valley(),
            "position": {
                "has_position": state.has_position,
                "side": position.get("side") if position else None,
                "contracts": float(position.get("contracts", 0)) if position else 0,
                "pnl": float(position.get("unrealizedPnl", 0)) if position else 0
            },
            "allocation": {
                "notional": float(state.notional_allocation),
                "margin": float(state.margin_allocation),
                "fragment_usd": float(state.position_fragment_usd),
                "fragment_eth": float(state.position_fragment_eth)
            },
            "short_positions": {
                "count": len(state.short_positions),
                "total_value": float(total_short_value),
                "original_total": float(len(state.short_positions) * state.position_fragment_usd),
                "unrealized_pnl": float(total_short_value - (len(state.short_positions) * state.position_fragment_usd)) if state.short_positions else 0
            },
            "compound_tracking": {
                "reset_count": state.reset_count,
                "initial_notional": float(state.initial_notional_allocation),
                "current_notional": float(state.notional_allocation),
                "total_growth": float(state.notional_allocation - state.initial_notional_allocation),
                "growth_percentage": float(((state.notional_allocation / state.initial_notional_allocation) - 1) * 100) if state.initial_notional_allocation > 0 else 0
            }
        }
    
    async def stop_strategy(self, symbol: str, close_position: bool = True):
        """Stop a running strategy"""
        if symbol not in self.strategies:
            logger.warning(f"No strategy running for {symbol}")
            return
        
        state = self.strategies[symbol]
        
        logger.info(f"Stopping strategy for {symbol}")
        
        # Close position if requested
        if close_position and state.has_position:
            logger.info("Closing position...")
            try:
                # Close all positions (long and short)
                orders = self.exchange_client.close_all_positions(symbol)
                if orders:
                    logger.success(f"All positions closed")
            except Exception as e:
                logger.error(f"Error closing position: {e}")
        
        # Remove strategy
        del self.strategies[symbol]
        logger.info(f"Strategy stopped for {symbol}")
