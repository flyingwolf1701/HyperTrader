"""
Strategy Manager - SIMPLIFIED LONG-ONLY VERSION
Removes all short position complexity while preserving core retracement logic
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

from ..core.unitTracker import UnitTracker, Phase
from ..core.websocket_client import HyperliquidWebSocketClient
from ..exchange.exchange_client import HyperliquidExchangeClient
from ..utils import settings


class StrategyState:
    """SIMPLIFIED: Long-only strategy state without short position tracking"""
    
    def __init__(self, symbol: str, position_size_usd: Decimal, unit_size_usd: Decimal, leverage: int = 25):
        # Configuration
        self.symbol = symbol
        self.position_size_usd = position_size_usd
        self.unit_size_usd = unit_size_usd
        self.leverage = leverage  # ETH is 25x on Hyperliquid
        
        # Position tracking
        self.notional_allocation = position_size_usd  # Total position value ($1000)
        self.margin_allocation = position_size_usd / Decimal(leverage)  # Margin required ($40 at 25x)
        self.initial_notional_allocation = position_size_usd
        self.initial_margin_allocation = position_size_usd / Decimal(leverage)
        
        # Fragment tracking - simplified
        self.position_fragment_usd = Decimal("0")  # USD value of fragment (25% of position)
        self.position_fragment_eth = Decimal("0")  # ETH amount of fragment (locked at peak)
        
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
        self.initial_eth_amount: Decimal = Decimal("0")  # Track initial ETH for fragment calculations
        
        # Unit tracker
        self.unit_tracker = UnitTracker(unit_size_usd=unit_size_usd)
        
        # SIMPLIFIED TRACKING: Track what fragments have been sold
        self.fragments_sold = {}  # Dict[units_from_peak, eth_amount]
        self.total_eth_sold = Decimal("0")   # Total ETH sold during retracement
    
    def calculate_position_fragment_at_peak(self, peak_price: Decimal):
        """Calculate 25% fragment at peak and LOCK IT"""
        # Get current position from exchange to calculate fragment
        fragment_usd = self.notional_allocation * Decimal("0.25")  # 25% fragment
        fragment_eth = fragment_usd / peak_price
        
        # Store fragment values
        self.position_fragment_usd = fragment_usd
        self.position_fragment_eth = fragment_eth
        
        logger.info(f"🔒 FRAGMENT LOCKED AT PEAK ${peak_price}:")
        logger.info(f"  Notional Value: ${self.notional_allocation}")
        logger.info(f"  Fragment USD: ${fragment_usd} (25%)")
        logger.info(f"  Fragment ETH: {fragment_eth:.6f} ETH")
        logger.info("  This ETH amount stays CONSTANT during retracement")
        
        return fragment_usd
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for persistence"""
        return {
            "symbol": self.symbol,
            "phase": self.unit_tracker.phase.value if self.unit_tracker.phase else "UNKNOWN",
            "position_size_usd": str(self.position_size_usd),
            "unit_size_usd": str(self.unit_size_usd),
            "leverage": self.leverage,
            "notional_allocation": str(self.notional_allocation),
            "margin_allocation": str(self.margin_allocation),
            "initial_notional_allocation": str(self.initial_notional_allocation),
            "initial_margin_allocation": str(self.initial_margin_allocation),
            "position_fragment_usd": str(self.position_fragment_usd),
            "position_fragment_eth": str(self.position_fragment_eth),
            "reset_count": self.reset_count,
            "pre_reset_notional": str(self.pre_reset_notional),
            "pre_reset_margin": str(self.pre_reset_margin),
            "last_recovery_unit": self.last_recovery_unit,
            "entry_price": str(self.entry_price) if self.entry_price else None,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "has_position": self.has_position,
            "initial_eth_amount": str(self.initial_eth_amount),
            "current_unit": self.unit_tracker.current_unit,
            "peak_unit": self.unit_tracker.peak_unit,
            "valley_unit": self.unit_tracker.valley_unit,
            "fragments_sold": {k: str(v) for k, v in self.fragments_sold.items()},
            "total_eth_sold": str(self.total_eth_sold),
        }


class StrategyManager:
    """SIMPLIFIED Strategy Manager - Long-only with fragment scaling"""
    
    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        self.ws_client = HyperliquidWebSocketClient(testnet=testnet)
        self.exchange_client = HyperliquidExchangeClient(testnet=testnet)
        self.strategies: Dict[str, StrategyState] = {}
        self.is_running = False
    
    async def start_strategy(
        self,
        symbol: str,
        position_size_usd: Decimal,
        unit_size_usd: Decimal,
        leverage: int = 25  # ETH is 25x on Hyperliquid
    ) -> bool:
        """Start a SIMPLIFIED long-only trading strategy"""
        try:
            logger.info("=" * 60)
            logger.info("HYPERTRADER - SIMPLIFIED LONG-ONLY STRATEGY")
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Notional Position: ${position_size_usd}")
            logger.info(f"Margin Required: ${position_size_usd / Decimal(leverage)} (at {leverage}x)")
            logger.info(f"Unit Size: ${unit_size_usd}")
            logger.info("=" * 60)
            
            # Check if strategy already exists
            if symbol in self.strategies:
                logger.warning(f"Strategy already running for {symbol}")
                return False
            
            # Create strategy state
            state = StrategyState(symbol, position_size_usd, unit_size_usd, leverage)
            self.strategies[symbol] = state
            
            # Check existing position
            existing_position = self.exchange_client.get_position(symbol)
            if existing_position:
                logger.warning(f"Existing position found for {symbol}")
                logger.info(f"Position: {existing_position.side} {existing_position.contracts} contracts")
                logger.info("Please close existing position before starting new strategy")
                return False
            
            # STEP 1: START WEBSOCKET MONITORING FIRST (before any trades)
            logger.info("\nStep 1: Starting WebSocket monitoring...")
            await self._start_monitoring_preparation(symbol, unit_size_usd, state)
            
            # STEP 2: Enter trade (100% long position)
            logger.info("\nStep 2: Opening 100% long position...")
            
            try:
                order = await self.exchange_client.buy_long_usd(
                    symbol=symbol,
                    usd_amount=position_size_usd,
                    leverage=leverage
                )
                logger.info(f"Order result: {order}")
            except Exception as e:
                logger.error(f"Error placing buy order: {e}")
                order = None
            
            if order:
                # Update state
                state.has_position = True
                state.entry_time = datetime.now()
                
                # Get entry price from order or current market
                if order and order.price and order.price != 0:
                    state.entry_price = order.price
                else:
                    state.entry_price = self.exchange_client.get_current_price(symbol)
                
                # Set entry price in unit tracker
                state.unit_tracker.entry_price = state.entry_price
                
                # Store initial ETH amount for fragment calculations
                if order and order.eth_amount:
                    state.initial_eth_amount = order.eth_amount
                else:
                    state.initial_eth_amount = position_size_usd / state.entry_price
                
                # Set phase to ADVANCE
                state.unit_tracker.phase = Phase.ADVANCE
                
                logger.success("Position opened successfully")
                logger.info(f"Entry Price: ${state.entry_price:.2f}")
                logger.info(f"ETH Amount: {state.initial_eth_amount:.6f} ETH")
                logger.info(f"Notional Value: ${state.notional_allocation}")
                logger.info(f"Margin Used: ${state.margin_allocation}")
                logger.info("Phase: ADVANCE")
                
                # STEP 3: Activate monitoring
                logger.info("\nStep 3: Activating price monitoring...")
                await self._activate_monitoring(symbol)
                
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
        """SIMPLIFIED ADVANCE phase - track peaks and execute retracement scaling"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        
        # Get current position
        position = self.exchange_client.get_position(symbol)
        if not position:
            logger.warning("No position found in ADVANCE phase")
            return
            
        current_price = self.exchange_client.get_current_price(symbol)
        
        # Check if we've reached a new peak
        if state.unit_tracker.current_unit == state.unit_tracker.peak_unit and state.unit_tracker.current_unit > 0:
            # NEW PEAK - calculate and LOCK fragment (only if not already calculated)
            if state.position_fragment_usd == Decimal("0"):
                state.calculate_position_fragment_at_peak(current_price)
                
                logger.success("📈 NEW PEAK REACHED:")
                logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
                logger.info(f"  🔒 Fragment LOCKED: ${state.position_fragment_usd} = {state.position_fragment_eth:.6f} ETH")
            else:
                logger.info(f"ADVANCE Phase - Peak Unit {state.unit_tracker.peak_unit}")
                logger.info(f"  🔒 Fragment Already Locked: ${state.position_fragment_usd} = {state.position_fragment_eth:.6f} ETH")
        else:
            # NOT at peak
            logger.info("ADVANCE Phase Update:")
            logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
            logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
            if state.position_fragment_usd > Decimal("0"):
                logger.info(f"  🔒 USING Locked Fragment: ${state.position_fragment_usd} = {state.position_fragment_eth:.6f} ETH")
            else:
                logger.info("  ⏳ No fragment locked yet (awaiting first peak)")
        
        # Check for phase transition to retracement
        units_from_peak = state.unit_tracker.get_units_from_peak()
        if units_from_peak <= -1:
            # Ensure we have a fragment locked before entering retracement
            if state.position_fragment_usd == Decimal("0"):
                logger.warning("🚨 Price dropped but no fragment locked - calculating emergency fragment")
                state.calculate_position_fragment_at_peak(current_price)
            
            logger.warning(f"💥 Price dropped {abs(units_from_peak)} unit(s) from peak")
            logger.warning(f"🔒 Fragment LOCKED: {state.position_fragment_eth:.6f} ETH")
            logger.info("Starting RETRACEMENT actions")
            await self.handle_retracement_phase(symbol)
    
    async def handle_retracement_phase(self, symbol: str):
        """SIMPLIFIED RETRACEMENT phase - scale down long positions only"""
        if symbol not in self.strategies:
            return
        
        state = self.strategies[symbol]
        units_from_peak = state.unit_tracker.get_units_from_peak()
        current_price = self.exchange_client.get_current_price(symbol)
        
        logger.info("=" * 60)
        logger.info(f"RETRACEMENT Phase - {abs(units_from_peak)} units from peak")
        logger.info(f"Current Price: ${current_price}")
        logger.info(f"Fragment ETH (locked): {state.position_fragment_eth:.6f} ETH")
        logger.info(f"Fragment USD (locked): ${state.position_fragment_usd}")
        logger.info("=" * 60)
        
        try:
            # Check if we already executed this retracement level
            if units_from_peak in state.fragments_sold:
                logger.info(f"Retracement action for {units_from_peak} already executed")
                return
            
            # SIMPLIFIED LONG-ONLY STRATEGY:
            if units_from_peak == -1:
                logger.info("📊 At -1: Holding position (no action)")
                return
                
            elif units_from_peak in [-2, -3, -4]:
                # Sell 25% fragment at each level
                eth_to_sell = state.position_fragment_eth  # 25% fragment
                action_desc = f"Sell 1 fragment (25%) at {units_from_peak}"
                
                logger.info(f"🔄 ACTION ({units_from_peak}): {action_desc}")
                logger.info(f"   ETH to sell: {eth_to_sell:.6f} ETH")
                
                # Execute sell
                sell_result = await self.exchange_client.sell_long_eth(
                    symbol=symbol,
                    eth_amount=eth_to_sell,
                    reduce_only=True
                )
                
                if sell_result:
                    cash_received = sell_result.usd_received or Decimal("0")
                    logger.success(f"✅ Sold {eth_to_sell:.6f} ETH → ${cash_received:.2f} cash")
                    
                    # Track the action
                    state.fragments_sold[units_from_peak] = eth_to_sell
                    state.total_eth_sold += eth_to_sell
                    
                    logger.info(f"📊 Fragment {abs(units_from_peak)-1}/3 sold")
                    logger.info(f"   Total ETH sold: {state.total_eth_sold:.6f}")
                    
                    # Display portfolio status
                    self._display_portfolio_status(state, current_price)
                
            elif units_from_peak == -5:
                # Sell remaining position
                position = self.exchange_client.get_position(symbol)
                if position and position.side == 'long':
                    remaining_contracts = abs(position.contracts)
                    
                    logger.warning("🔄 SELLING REMAINDER at -5 from peak")
                    logger.info(f"   Selling: {remaining_contracts:.6f} ETH (remainder)")
                    
                    sell_result = await self.exchange_client.sell_long_eth(
                        symbol=symbol,
                        eth_amount=remaining_contracts,
                        reduce_only=True
                    )
                    
                    if sell_result:
                        cash_received = sell_result.usd_received or Decimal("0")
                        logger.success(f"✅ Sold remainder {remaining_contracts:.6f} ETH → ${cash_received:.2f} cash")
                        
                        # Track the action
                        state.fragments_sold[units_from_peak] = remaining_contracts
                        state.total_eth_sold += remaining_contracts
                        
                        logger.info("📊 Position now 100% CASH")
                        self._display_portfolio_status(state, current_price)
                
            elif units_from_peak <= -6:
                # Start valley tracking
                if state.unit_tracker.valley_unit == 0:
                    state.unit_tracker.valley_unit = state.unit_tracker.current_unit
                    logger.info(f"📉 VALLEY TRACKING STARTED at unit {state.unit_tracker.valley_unit}")
                
                # Update valley if we've made a new low
                if state.unit_tracker.current_unit < state.unit_tracker.valley_unit:
                    state.unit_tracker.valley_unit = state.unit_tracker.current_unit
                    logger.info(f"📉 NEW VALLEY: Unit {state.unit_tracker.valley_unit}")
                
                # Check for recovery (+2 from valley)
                units_from_valley = state.unit_tracker.get_units_from_valley()
                if units_from_valley >= 2:
                    logger.info(f"📈 RECOVERY: Price at +{units_from_valley} from valley")
                    state.unit_tracker.phase = Phase.RECOVERY
                    await self.handle_recovery_phase(symbol)
            
        except Exception as e:
            logger.error(f"❌ Error in RETRACEMENT phase: {e}")
    
    def _display_portfolio_status(self, state: StrategyState, current_price: Decimal):
        """Display current portfolio composition"""
        try:
            position = self.exchange_client.get_position(state.symbol)
            
            if position:
                long_contracts = abs(position.contracts)
                long_value = long_contracts * current_price
                
                logger.info("📊 PORTFOLIO STATUS:")
                logger.info(f"   Long Position: {long_contracts:.6f} ETH (${long_value:.2f})")
                logger.info(f"   Cash from sales: ${state.total_eth_sold * current_price:.2f} (approx)")
                logger.info(f"   Total ETH sold: {state.total_eth_sold:.6f} ETH")
                
                # Calculate percentage sold
                if state.initial_eth_amount > 0:
                    pct_sold = (state.total_eth_sold / state.initial_eth_amount) * 100
                    logger.info(f"   Position scaled down: {pct_sold:.1f}%")
            else:
                logger.info("📊 PORTFOLIO STATUS: 100% Cash (no position)")
                
        except Exception as e:
            logger.warning(f"Could not calculate portfolio status: {e}")
    
    async def handle_recovery_phase(self, symbol: str):
        """SIMPLIFIED RECOVERY phase - buy back fragments incrementally"""
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
        
        logger.warning("=" * 60)
        logger.warning(f"📈 RECOVERY - {units_from_valley} units from valley")
        logger.info(f"Current Price: ${current_price}")
        logger.warning("=" * 60)
        
        try:
            if units_from_valley in [2, 3, 4]:
                # Buy back fragments incrementally
                fragment_num = units_from_valley - 1  # 2->1, 3->2, 4->3
                cash_per_fragment = state.position_fragment_usd  # 25% each
                
                logger.info(f"🟢 BUYING BACK FRAGMENT #{fragment_num}")
                logger.info(f"   Using ${cash_per_fragment:.2f} to buy ETH")
                
                buy_result = await self.exchange_client.buy_long_usd(
                    symbol=symbol,
                    usd_amount=cash_per_fragment,
                    leverage=state.leverage
                )
                
                if buy_result:
                    eth_bought = buy_result.eth_amount if hasattr(buy_result, 'eth_amount') else cash_per_fragment / current_price
                    logger.success(f"✅ Bought {eth_bought:.6f} ETH with ${cash_per_fragment:.2f}")
                    self._display_portfolio_status(state, current_price)
                    
            elif units_from_valley >= 5:
                # Buy back final fragment and trigger reset
                cash_per_fragment = state.position_fragment_usd
                
                logger.info("🟢 BUYING BACK FINAL FRAGMENT")
                logger.info(f"   Using ${cash_per_fragment:.2f} to buy ETH")
                
                buy_result = await self.exchange_client.buy_long_usd(
                    symbol=symbol,
                    usd_amount=cash_per_fragment,
                    leverage=state.leverage
                )
                
                if buy_result:
                    eth_bought = buy_result.eth_amount if hasattr(buy_result, 'eth_amount') else cash_per_fragment / current_price
                    logger.success(f"✅ Bought {eth_bought:.6f} ETH with ${cash_per_fragment:.2f}")
                    logger.info("📊 Position now 100% LONG")
                    
                    # Trigger RESET mechanism
                    logger.info("🔄 Triggering RESET mechanism")
                    await self.handle_reset_mechanism(symbol)
                
        except Exception as e:
            logger.error(f"Error in RECOVERY phase: {e}")
    
    async def handle_reset_mechanism(self, symbol: str):
        """SIMPLIFIED RESET mechanism with compound growth tracking"""
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
            current_notional_value = abs(position.contracts) * current_price
            current_margin_value = current_notional_value / Decimal(state.leverage)
            
            # Calculate compound growth
            cycle_growth = current_notional_value - state.notional_allocation
            growth_percentage = (cycle_growth / state.notional_allocation) * 100
            
            logger.info("Cycle Summary:")
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
            
            # Clear tracking variables
            state.fragments_sold.clear()
            state.total_eth_sold = Decimal("0")
            
            # RESET unit tracking variables
            state.unit_tracker.current_unit = 0
            state.unit_tracker.peak_unit = 0
            state.unit_tracker.valley_unit = 0
            
            # Update entry price and reset fragment values
            state.entry_price = current_price
            state.unit_tracker.entry_price = current_price
            state.position_fragment_usd = Decimal("0")
            state.position_fragment_eth = Decimal("0")
            state.initial_eth_amount = abs(position.contracts)
            
            # Set phase to ADVANCE
            state.unit_tracker.phase = Phase.ADVANCE
            state.reset_count += 1
            state.last_recovery_unit = 0
            
            logger.success("🔄 RESET Complete!")
            logger.info("New Baseline:")
            logger.info(f"  Notional Value: ${state.notional_allocation:.2f}")
            logger.info(f"  Margin Value: ${state.margin_allocation:.2f}")
            logger.info(f"  Entry Price: ${state.entry_price:.2f}")
            logger.info(f"  ETH Amount: {state.initial_eth_amount:.6f} ETH")
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
        
        logger.info(f"🔄 Unit changed: {previous_unit} → {state.unit_tracker.current_unit}")
        
        # Handle based on current phase - SIMPLIFIED
        if state.unit_tracker.phase == Phase.ADVANCE:
            await self.handle_advance_phase(symbol)
        elif state.unit_tracker.phase == Phase.RECOVERY:
            await self.handle_recovery_phase(symbol)
    
    async def _start_monitoring_preparation(self, symbol: str, unit_size_usd: Decimal, state: StrategyState):
        """STEP 1: Connect WebSocket and prepare monitoring"""
        try:
            logger.info("[WEBSOCKET] Connecting to WebSocket...")
            
            # Connect WebSocket if not connected
            if not self.ws_client.is_connected:
                await self.ws_client.connect()
                logger.success("[OK] WebSocket connected")
            
            # Extract coin from symbol  
            coin = symbol.split("/")[0]  # ETH from ETH/USDC:USDC
            
            # Subscribe to trades (but don't activate callbacks yet)
            await self.ws_client.subscribe_to_trades(
                coin, 
                unit_size_usd,
                unit_tracker=state.unit_tracker,
                price_callback=None  # No callback yet - we'll add it after trade
            )
            
            logger.success(f"[OK] Subscribed to {coin} price feed")
            logger.info("WebSocket ready - waiting for trade execution...")
            
        except Exception as e:
            logger.error(f"❌ Error preparing monitoring: {e}")
            raise
    
    async def _activate_monitoring(self, symbol: str):
        """STEP 3: Activate price change callbacks"""
        try:
            # Get the strategy state
            state = self.strategies[symbol]
            coin = symbol.split("/")[0]
            
            # Create callback for price changes
            async def price_change_callback(new_price: Decimal):
                await self.monitor_price_change(symbol, new_price)
            
            # Update the existing subscription with the callback
            if coin in self.ws_client.price_callbacks:
                self.ws_client.price_callbacks[coin] = price_change_callback
                logger.success(f"✅ Price monitoring activated for {coin}")
                
                # Show current boundaries for user info
                if state.unit_tracker.entry_price:
                    boundaries = state.unit_tracker.get_current_unit_boundaries()
                    logger.info("🎯 Unit boundaries:")
                    logger.info(f"  Next +1 unit: ${boundaries['next_up']:.2f}")
                    logger.info(f"  Next -1 unit: ${boundaries['next_down']:.2f}")
            else:
                logger.warning(f"⚠️ No price callback found for {coin} - monitoring may not work")
            
        except Exception as e:
            logger.error(f"❌ Error activating monitoring: {e}")
    
    async def get_strategy_status(self, symbol: str) -> Dict[str, Any]:
        """Get simplified strategy status"""
        if symbol not in self.strategies:
            return {"error": f"No strategy found for {symbol}"}
        
        state = self.strategies[symbol]
        
        # Get current position from exchange
        position = self.exchange_client.get_position(symbol)
        current_price = self.exchange_client.get_current_price(symbol)
        
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
                "side": position.side if position else None,
                "contracts": float(position.contracts) if position else 0,
                "pnl": float(position['unrealized_pnl']) if position else 0
            },
            "allocation": {
                "notional": float(state.notional_allocation),
                "margin": float(state.margin_allocation),
                "fragment_usd": float(state.position_fragment_usd),
                "fragment_eth": float(state.position_fragment_eth)
            },
            "retracement_progress": {
                "fragments_sold": len(state.fragments_sold),
                "total_eth_sold": float(state.total_eth_sold),
                "fragments_remaining": 3 - len([k for k in state.fragments_sold.keys() if k in [-2, -3, -4]])
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
                position = self.exchange_client.get_position(symbol)
                if position:
                    remaining_eth = abs(position.contracts)
                    close_result = await self.exchange_client.sell_long_eth(
                        symbol=symbol,
                        eth_amount=remaining_eth,
                        reduce_only=True
                    )
                    if close_result:
                        logger.success("Position closed")
            except Exception as e:
                logger.error(f"Error closing position: {e}")
        
        # Remove strategy
        del self.strategies[symbol]
        logger.info(f"Strategy stopped for {symbol}")
