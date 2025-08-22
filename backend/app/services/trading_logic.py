# backend/app/services/trading_logic.py

import logging
from decimal import Decimal
import asyncio

from app.models.state import system_state
from app.api.websockets import websocket_manager
from app.models.state import SystemState, PhaseType
from app.services.exchange import exchange_manager, OrderResult
from app.schemas.trade_history import TradeHistory
from app.schemas.plan import TradingPlan
from app.db.session import get_db_session
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

async def save_trade_to_db(
    order_result: OrderResult,
    symbol: str,
    order_type: str,
    side: str,
    amount: float,
    price: float = None,
    reduce_only: bool = False,
    trading_plan_id: int = None,
    current_unit: int = None,
    current_phase: str = None,
    units_from_peak: int = None,
    units_from_valley: int = None
):
    """Save trade details to database for tracking."""
    try:
        async with get_db_session() as db:
            trade_record = TradeHistory(
                trading_plan_id=trading_plan_id,
                symbol=symbol,
                order_id=order_result.order_id,
                order_type=order_type,
                side=side,
                amount=Decimal(str(amount)),
                price=Decimal(str(price)) if price else None,
                average_price=order_result.average_price,
                cost=order_result.cost,
                success=order_result.success,
                reduce_only=reduce_only,
                error_message=order_result.error_message,
                current_unit=current_unit,
                current_phase=current_phase,
                units_from_peak=units_from_peak,
                units_from_valley=units_from_valley
            )
            
            db.add(trade_record)
            await db.commit()
            
            logger.info(f"💾 TRADE SAVED TO DB: {side} {amount} {symbol} at ${price} - Success: {order_result.success}")
            
    except Exception as e:
        logger.error(f"Failed to save trade to database: {e}", exc_info=True)

async def on_price_update(price: float):
    """
    Entry point for price updates from the exchange.
    Calculates the unit change and triggers the main trading logic.
    """
    current_price = Decimal(str(price))
    
    # Get active trading plans from database
    async with get_db_session() as db:
        try:
            # Find all active trading plans
            result = await db.execute(
                select(TradingPlan).where(
                    TradingPlan.is_active == "active"
                )
            )
            active_plans = result.scalars().all()
            
            if not active_plans:
                logger.debug(f"Price update ${current_price} - No active trading plans")
                return
            
            # Process each active trading plan
            for trading_plan in active_plans:
                await process_price_update_for_plan(trading_plan, current_price, db)
                
        except Exception as e:
            logger.error(f"Error processing price updates: {e}", exc_info=True)

async def process_price_update_for_plan(trading_plan: TradingPlan, current_price: Decimal, db):
    """
    Process price update for a specific trading plan.
    """
    try:
        # Load system state from database
        state = SystemState(**trading_plan.system_state)
        state.trading_plan_id = trading_plan.id  # Ensure trading plan ID is set
        
        if current_price == state.current_price:
            return

        logger.info(f"📊 Price update for {state.symbol}: ${current_price} (was ${state.current_price})")
        state.current_price = current_price
        
        if state.unit_value == 0:
            logger.warning(f"Unit value is zero for {state.symbol}, cannot calculate unit change.")
            return
            
        price_change = current_price - state.entry_price
        new_unit = int(price_change / state.unit_value)
        
        logger.info(f"Price change from entry: ${price_change}")
        logger.info(f"Unit calculation: {price_change} / {state.unit_value} = {price_change / state.unit_value} -> {new_unit}")

        if new_unit != state.current_unit:
            logger.info(f"🚨 PRICE UPDATE TRIGGERED UNIT CHANGE for {state.symbol}: {state.current_unit} -> {new_unit}")
            
            # Process the unit change
            updated_state = await trading_logic.on_unit_change(state, new_unit, current_price)
            
            # Save updated state back to database
            await db.execute(
                update(TradingPlan)
                .where(TradingPlan.id == trading_plan.id)
                .values(
                    system_state=updated_state.dict(),
                    current_phase=updated_state.current_phase
                )
            )
            await db.commit()
            
            # Broadcast via websocket
            await websocket_manager.broadcast(updated_state.model_dump_json())
        else:
            logger.info(f"No unit change for {state.symbol} - staying at unit {state.current_unit}")
            
            # Still update the current price in database
            state.current_price = current_price
            await db.execute(
                update(TradingPlan)
                .where(TradingPlan.id == trading_plan.id)
                .values(system_state=state.dict())
            )
            await db.commit()
            
    except Exception as e:
        logger.error(f"Error processing price update for plan {trading_plan.id}: {e}", exc_info=True)


class TradingLogic:
    """
    Core trading logic implementing the four-phase hedging strategy.
    This is the heart of the HyperTrader system.
    """
    
    def __init__(self):
        self.exchange = exchange_manager
    
    async def on_unit_change(self, state: SystemState, new_unit: int, current_price: Decimal) -> SystemState:
        """
        Central traffic cop function called when unit changes.
        Determines phase and calls appropriate handler.
        """
        logger.info(f"=== UNIT CHANGE DETECTED ===")
        logger.info(f"Symbol: {state.symbol}")
        logger.info(f"Unit change: {state.current_unit} -> {new_unit}")
        logger.info(f"Current price: ${current_price}")
        logger.info(f"Entry price: ${state.entry_price}")
        logger.info(f"Unit value: ${state.unit_value}")
        logger.info(f"Price change from entry: ${current_price - state.entry_price}")
        
        state.current_unit = new_unit
        state = self._update_peak_valley_tracking(state, current_price)
        required_phase = self._determine_phase(state)
        
        if state.current_phase != required_phase:
            logger.info(f"*** PHASE CHANGE *** {state.symbol}: {state.current_phase} -> {required_phase}")
            state.current_phase = required_phase
        else:
            logger.info(f"Staying in {state.current_phase} phase")
        
        try:
            logger.info(f"Executing {state.current_phase} phase handler...")
            if state.current_phase == "advance":
                state = await self._handle_advance_phase(state, current_price)
            elif state.current_phase == "retracement":
                state = await self._handle_retracement_phase(state, current_price)
            elif state.current_phase == "decline":
                state = await self._handle_decline_phase(state, current_price)
            elif state.current_phase == "recovery":
                state = await self._handle_recovery_phase(state, current_price)
            logger.info(f"Phase handler {state.current_phase} completed")
        except Exception as e:
            logger.error(f"Error in phase handler for {state.symbol}: {e}", exc_info=True)
            raise
        
        if state.is_reset_condition_met():
            logger.info(f"Reset conditions met for {state.symbol}")
            state = await self._perform_system_reset(state, current_price)
        
        return state
    
    def _update_peak_valley_tracking(self, state: SystemState, current_price: Decimal) -> SystemState:
        if state.long_invested > 0:
            if state.peak_unit is None or state.current_unit > state.peak_unit:
                state.peak_unit = state.current_unit
                state.peak_price = current_price
        else:
            state.peak_unit, state.peak_price = None, None
        
        if state.hedge_short > 0:
            if state.valley_unit is None or state.current_unit < state.valley_unit:
                state.valley_unit = state.current_unit
                state.valley_price = current_price
        else:
            state.valley_unit, state.valley_price = None, None
        
        return state
    
    def _determine_phase(self, state: SystemState) -> PhaseType:
        total_long = state.long_invested + state.long_cash
        total_hedge = state.hedge_long + state.hedge_short
        
        # Use a small tolerance for float comparisons
        is_long_full = abs(state.long_invested - total_long) < Decimal('0.01')
        is_hedge_full_long = abs(state.hedge_long - total_hedge) < Decimal('0.01') and state.hedge_short == 0
        is_long_cashed = state.long_invested == 0
        is_hedge_full_short = state.hedge_long == 0 and abs(state.hedge_short - total_hedge) < Decimal('0.01')

        if is_long_full and is_hedge_full_long: return "advance"
        if is_long_cashed and is_hedge_full_short: return "decline"
        if state.hedge_short > 0 and state.valley_unit is not None: return "recovery"
        
        return "retracement"
    
    async def _handle_advance_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        logger.debug(f"Handling ADVANCE phase for {state.symbol}")
        return state
    
    async def _handle_retracement_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        logger.info(f"=== HANDLING RETRACEMENT PHASE ===")
        logger.info(f"Symbol: {state.symbol}")
        
        if state.peak_unit is None:
            logger.warning(f"No peak unit for {state.symbol} in retracement")
            return state
        
        units_from_peak = state.current_unit - state.peak_unit
        choppy = state.is_choppy_trading_active()
        
        logger.info(f"Peak unit: {state.peak_unit}")
        logger.info(f"Current unit: {state.current_unit}")
        logger.info(f"Units from peak: {units_from_peak}")
        logger.info(f"Choppy trading: {choppy}")
        
        if not choppy and units_from_peak == -1:
            logger.info(f"Long waiting for confirmation at {units_from_peak} from peak")
        elif units_from_peak <= -2 or (choppy and units_from_peak <= -1):
            logger.info(f"Triggering long scaling: units_from_peak={units_from_peak}, choppy={choppy}")
            state = await self._scale_long_allocation(state, units_from_peak, current_price)
        else:
            logger.info(f"No long scaling triggered")
        
        if units_from_peak <= -1:
            logger.info(f"Triggering hedge scaling")
            state = await self._scale_hedge_allocation(state, units_from_peak, current_price)
        else:
            logger.info(f"No hedge scaling triggered")
        
        return state
    
    async def _handle_decline_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        logger.debug(f"Handling DECLINE phase for {state.symbol}")
        return state
    
    async def _handle_recovery_phase(self, state: SystemState, current_price: Decimal) -> SystemState:
        logger.debug(f"Handling RECOVERY phase for {state.symbol}")
        if state.valley_unit is None:
            logger.warning(f"No valley unit for {state.symbol} in recovery")
            return state
            
        units_from_valley = state.current_unit - state.valley_unit
        choppy = state.is_choppy_trading_active()
        
        if not choppy and units_from_valley == 1:
            logger.debug(f"Long waiting for confirmation at {units_from_valley} from valley")
        elif units_from_valley >= 2 or (choppy and units_from_valley >= 1):
            state = await self._re_enter_long_allocation(state, units_from_valley, current_price)
        
        if units_from_valley >= 1:
            state = await self._unwind_hedge_shorts(state, units_from_valley, current_price)
            
        return state
    
    async def _scale_long_allocation(self, state: SystemState, units_from_peak: int, current_price: Decimal) -> SystemState:
        total_long = state.long_invested + state.long_cash
        if total_long == 0: return state
        
        target_percent = max(0, 100 + (units_from_peak + 2) * 25)
        target_invested = total_long * (Decimal(str(target_percent)) / 100)
        amount_to_sell = state.long_invested - target_invested
        
        if amount_to_sell > state.MIN_TRADE_VALUE:
            pos_size = float(amount_to_sell / current_price)
            logger.info(f"=== SCALING LONG ALLOCATION ===")
            logger.info(f"Amount to sell: ${amount_to_sell:.2f}")
            logger.info(f"Position size: {pos_size:.6f}")
            logger.info(f"Current price: ${current_price}")
            
            res = await self.exchange.place_order(state.symbol, "market", "sell", pos_size, reduce_only=True)
            logger.info(f"Order result: success={res.success}, order_id={res.order_id}")
            
            # Save trade to database
            await save_trade_to_db(
                res, state.symbol, "market", "sell", pos_size, float(current_price),
                reduce_only=True, trading_plan_id=state.trading_plan_id,
                current_unit=state.current_unit, current_phase=state.current_phase,
                units_from_peak=units_from_peak
            )
            
            if res.success:
                actual = res.cost or amount_to_sell
                state.long_invested -= actual
                state.long_cash += actual
                logger.info(f"✅ LONG SCALED: sold ${actual:.2f}")
                logger.info(f"New long_invested: ${state.long_invested:.2f}")
                logger.info(f"New long_cash: ${state.long_cash:.2f}")
            else:
                logger.error(f"❌ FAILED to scale long: {res.error_message}")
        else:
            logger.info(f"Skipping long scale - amount ${amount_to_sell:.2f} < min trade ${state.MIN_TRADE_VALUE}")
        return state
    
    async def _scale_hedge_allocation(self, state: SystemState, units_from_peak: int, current_price: Decimal) -> SystemState:
        total_hedge = state.hedge_long + state.hedge_short
        if total_hedge == 0: return state
        
        units_down = abs(units_from_peak)
        target_long_p = max(0, 100 - units_down * 25)
        target_short_p = min(100, units_down * 25)
        
        target_long_amt = total_hedge * (Decimal(str(target_long_p)) / 100)
        target_short_amt = total_hedge * (Decimal(str(target_short_p)) / 100)
        
        long_change = target_long_amt - state.hedge_long
        short_change = target_short_amt - state.hedge_short
        
        if long_change < -state.MIN_TRADE_VALUE:
            pos_size = float(abs(long_change) / current_price)
            logger.info(f"=== REDUCING HEDGE LONG ===")
            logger.info(f"Long change: ${long_change:.2f}")
            logger.info(f"Position size: {pos_size:.6f}")
            
            res = await self.exchange.place_order(state.symbol, "market", "sell", pos_size, reduce_only=True)
            logger.info(f"Order result: success={res.success}, order_id={res.order_id}")
            
            # Save trade to database
            await save_trade_to_db(
                res, state.symbol, "market", "sell", pos_size, float(current_price),
                reduce_only=True, trading_plan_id=state.trading_plan_id,
                current_unit=state.current_unit, current_phase=state.current_phase,
                units_from_peak=units_from_peak
            )
            
            if res.success:
                actual = res.cost or abs(long_change)
                state.hedge_long -= actual
                logger.info(f"✅ HEDGE LONG REDUCED by ${actual:.2f}")
                logger.info(f"New hedge_long: ${state.hedge_long:.2f}")
            else:
                logger.error(f"❌ FAILED to reduce hedge long: {res.error_message}")

        if short_change > state.MIN_TRADE_VALUE:
            pos_size = float(short_change / current_price)
            logger.info(f"=== INCREASING HEDGE SHORT ===")
            logger.info(f"Short change: ${short_change:.2f}")
            logger.info(f"Position size: {pos_size:.6f}")
            
            res = await self.exchange.place_order(state.symbol, "market", "sell", pos_size)
            logger.info(f"Order result: success={res.success}, order_id={res.order_id}")
            
            # Save trade to database
            await save_trade_to_db(
                res, state.symbol, "market", "sell", pos_size, float(current_price),
                reduce_only=False, trading_plan_id=state.trading_plan_id,
                current_unit=state.current_unit, current_phase=state.current_phase,
                units_from_peak=units_from_peak
            )
            
            if res.success:
                actual = res.cost or short_change
                state.hedge_short += actual
                logger.info(f"✅ HEDGE SHORT INCREASED by ${actual:.2f}")
                logger.info(f"New hedge_short: ${state.hedge_short:.2f}")
            else:
                logger.error(f"❌ FAILED to increase hedge short: {res.error_message}")
        else:
            logger.info(f"Skipping short increase - change ${short_change:.2f} < min trade ${state.MIN_TRADE_VALUE}")
        
        return state

    async def _re_enter_long_allocation(self, state: SystemState, units_from_valley: int, current_price: Decimal) -> SystemState:
        total_long = state.long_invested + state.long_cash
        if total_long == 0 or state.long_cash == 0: return state
        
        target_percent = min(100, (units_from_valley - 1) * 25)
        target_invested = total_long * (Decimal(str(target_percent)) / 100)
        amount_to_buy = target_invested - state.long_invested
        
        if amount_to_buy > state.MIN_TRADE_VALUE and amount_to_buy <= state.long_cash:
            pos_size = float(amount_to_buy / current_price)
            res = await self.exchange.place_order(state.symbol, "market", "buy", pos_size)
            
            # Save trade to database
            await save_trade_to_db(
                res, state.symbol, "market", "buy", pos_size, float(current_price),
                reduce_only=False, trading_plan_id=state.trading_plan_id,
                current_unit=state.current_unit, current_phase=state.current_phase,
                units_from_valley=units_from_valley
            )
            
            if res.success:
                actual = res.cost or amount_to_buy
                state.long_invested += actual
                state.long_cash -= actual
                logger.info(f"Long re-entered: bought ${actual:.2f}")
            else:
                logger.error(f"❌ FAILED to re-enter long: {res.error_message}")
        return state
    
    async def _unwind_hedge_shorts(self, state: SystemState, units_from_valley: int, current_price: Decimal) -> SystemState:
        if state.hedge_short == 0: return state
        
        total_hedge = state.hedge_long + state.hedge_short
        target_short_p = max(0, 100 - units_from_valley * 25)
        target_short_amt = total_hedge * (Decimal(str(target_short_p)) / 100)
        short_reduction = state.hedge_short - target_short_amt
        
        if short_reduction > state.MIN_TRADE_VALUE:
            pos_size = float(short_reduction / current_price)
            res = await self.exchange.place_order(state.symbol, "market", "buy", pos_size, reduce_only=True)
            
            # Save trade to database
            await save_trade_to_db(
                res, state.symbol, "market", "buy", pos_size, float(current_price),
                reduce_only=True, trading_plan_id=state.trading_plan_id,
                current_unit=state.current_unit, current_phase=state.current_phase,
                units_from_valley=units_from_valley
            )
            
            if res.success:
                actual = res.cost or short_reduction
                state.hedge_short -= actual
                state.hedge_long += actual
                logger.info(f"Hedge shorts unwound: covered ${actual:.2f}")
            else:
                logger.error(f"❌ FAILED to unwind hedge shorts: {res.error_message}")
        return state

    async def _perform_system_reset(self, state: SystemState, current_price: Decimal) -> SystemState:
        logger.info(f"Performing system reset for {state.symbol}")
        try:
            total_value = state.get_total_portfolio_value()
            allocation_amount = total_value / 2
            
            state.current_unit, state.peak_unit, state.valley_unit = 0, None, None
            state.peak_price, state.valley_price = None, None
            
            state.long_invested = allocation_amount
            state.long_cash = Decimal("0")
            state.hedge_long = allocation_amount
            state.hedge_short = Decimal("0")
            
            state.entry_price = current_price
            state.unit_value = (total_value * state.UNIT_PERCENTAGE) / state.leverage
            state.current_phase = "advance"
            
            # Update the initial value for the next reset cycle
            state.initial_portfolio_value = total_value
            state.realized_pnl = Decimal("0")
            
            logger.info(f"System reset complete. New portfolio value: ${total_value:.2f}")
        except Exception as e:
            logger.error(f"Error during system reset: {e}", exc_info=True)
            raise
        return state

# Global trading logic instance
trading_logic = TradingLogic()
