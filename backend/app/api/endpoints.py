from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete, func
from typing import List, Optional
import logging
from decimal import Decimal
import json
from datetime import datetime

from app.db.session import get_db_session
from app.models.state import SystemState, TradingPlanCreate, TradingPlanUpdate
from app.core.config import settings
from app.schemas import TradingPlan, UserFavorite
from app.services.exchange import exchange_manager, MarketInfo

logger = logging.getLogger(__name__)

router = APIRouter()


# Trading Plan Endpoints
@router.post("/trade/start", response_model=dict)
async def start_trading_plan(
    plan_data: TradingPlanCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Start a new trading plan based on a desired position size in USD.
    """
    try:
        # --- Symbol Formatting ---
        symbol_to_use = plan_data.symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"
        logger.info(f"Received trade request for {plan_data.symbol}, using formatted symbol {symbol_to_use}")

        # --- Validation ---
        if not exchange_manager.is_market_available(symbol_to_use):
            raise HTTPException(status_code=400, detail=f"Market {symbol_to_use} is not available")
        
        current_price = await exchange_manager.get_current_price(symbol_to_use)
        if current_price is None:
            raise HTTPException(status_code=503, detail=f"Unable to get current price for {symbol_to_use}")
        
        # --- Logic: Calculate based on position_size_usd ---
        total_position_value = plan_data.position_size_usd
        amount_in_coins = total_position_value / current_price
        required_margin = total_position_value / plan_data.leverage
        amount_rounded = round(float(amount_in_coins), 6)
        
        logger.info(f"Order calc: position_size=${total_position_value}, leverage={plan_data.leverage}, price=${current_price}, amount_coins={amount_rounded}, required_margin=${required_margin:.2f}")

        # --- FIX: Set Leverage Before Placing the Order ---
        try:
            await exchange_manager.exchange.set_leverage(plan_data.leverage, symbol_to_use)
            logger.info(f"Successfully set leverage to {plan_data.leverage} for {symbol_to_use}")
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol_to_use}: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"Failed to set leverage: {str(e)}")
        # --- END FIX ---

        # --- Place Order ---
        order_result = await exchange_manager.place_order(
            symbol=symbol_to_use,
            order_type="market",
            side="buy",
            amount=amount_rounded,
            price=current_price 
        )
        
        if not order_result.success:
            raise HTTPException(status_code=503, detail=f"Failed to place initial order: {order_result.error_message}")
        
        # --- Create State ---
        entry_price = order_result.average_price or current_price
        actual_cost = order_result.cost or total_position_value
        # Calculate USD value per unit based on user-defined unit_size
        unit_value = (plan_data.unit_size * plan_data.position_size_usd) / (current_price * 100)  # Example calculation
        
        system_state = SystemState(
            symbol=symbol_to_use,
            entry_price=entry_price,
            unit_size=plan_data.unit_size,
            unit_value=unit_value,
            required_margin=required_margin,
            leverage=plan_data.leverage,
            long_invested=actual_cost / 2,
            long_cash=Decimal("0"),
            hedge_long=actual_cost / 2,
            hedge_short=Decimal("0")
        )
        
        trading_plan = TradingPlan(
            symbol=symbol_to_use,
            system_state=system_state.model_dump_json_safe(),
            initial_margin=float(required_margin),
            leverage=plan_data.leverage,
            unit_size=float(plan_data.unit_size),
            current_phase=system_state.current_phase
        )
        
        db.add(trading_plan)
        await db.commit()
        await db.refresh(trading_plan)
        
        logger.info(f"Started new trading plan for {symbol_to_use} with ID {trading_plan.id}")
        
        system_state_dict = system_state.dict()
        for key, value in system_state_dict.items():
            if isinstance(value, Decimal):
                system_state_dict[key] = float(value)

        return {
            "success": True,
            "plan_id": trading_plan.id,
            "symbol": symbol_to_use,
            "entry_price": float(entry_price),
            "position_size_usd": float(total_position_value),
            "required_margin": float(required_margin),
            "order_id": order_result.order_id,
            "system_state": system_state_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting trading plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/trade/state/{symbol}", response_model=dict)
async def get_trading_state(
    symbol: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get current trading state for a symbol"""
    try:
        symbol_to_use = symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"

        result = await db.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol_to_use,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active trading plan found for {symbol_to_use}"
            )
        
        system_state = SystemState(**trading_plan.system_state)
        
        current_price = await exchange_manager.get_current_price(symbol_to_use)
        
        if current_price:
            price_change = current_price - system_state.entry_price
            position_value = system_state.long_invested + system_state.hedge_long
            if system_state.entry_price > 0:
                unrealized_pnl = (price_change / system_state.entry_price) * position_value
                system_state.unrealized_pnl = unrealized_pnl
        
        system_state_dict = system_state.dict()
        for key, value in system_state_dict.items():
            if isinstance(value, Decimal):
                system_state_dict[key] = float(value)

        return {
            "plan_id": trading_plan.id,
            "system_state": system_state_dict,
            "current_price": float(current_price) if current_price else None,
            "created_at": trading_plan.created_at.isoformat(),
            "updated_at": trading_plan.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trading state for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.put("/trade/state/{symbol}", response_model=dict)
async def update_trading_state(
    symbol: str,
    update_data: TradingPlanUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """Update trading state (used by the internal WebSocket/trading logic handler)"""
    try:
        symbol_to_use = symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"

        result = await db.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol_to_use,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active trading plan found for {symbol_to_use}"
            )
        
        system_state_dict = trading_plan.system_state.copy()
        
        update_fields = update_data.dict(exclude_unset=True)
        for field, value in update_fields.items():
            if value is not None:
                if isinstance(value, (int, float, Decimal)):
                    system_state_dict[field] = str(value)
                else:
                    system_state_dict[field] = value
        
        await db.execute(
            update(TradingPlan)
            .where(TradingPlan.id == trading_plan.id)
            .values(
                system_state=system_state_dict,
                current_phase=system_state_dict.get('current_phase', trading_plan.current_phase)
            )
        )
        await db.commit()
        
        return {"success": True, "updated_fields": list(update_fields.keys())}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating trading state for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


# Exchange Info Endpoints
@router.get("/exchange/pairs", response_model=List[dict])
async def get_exchange_pairs():
    try:
        markets = await exchange_manager.fetch_markets()
        pairs = []
        for market in markets:
            if market.active:
                pairs.append({
                    "symbol": market.symbol, "base": market.base, "quote": market.quote,
                    "min_amount": float(market.min_amount) if market.min_amount else None,
                    "max_amount": float(market.max_amount) if market.max_amount else None,
                    "min_price": float(market.min_price) if market.min_price else None,
                    "max_price": float(market.max_price) if market.max_price else None,
                })
        return pairs
    except Exception as e:
        logger.error(f"Error fetching exchange pairs: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Unable to fetch market data: {str(e)}")

@router.get("/exchange/price/{symbol}")
async def get_current_price(symbol: str):
    try:
        symbol_to_use = symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"
        price = await exchange_manager.get_current_price(symbol_to_use)
        if price is None:
            raise HTTPException(status_code=404, detail=f"Unable to get price for {symbol_to_use}")
        return {"symbol": symbol_to_use, "price": float(price)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.get("/exchange/balances")
async def get_account_balances():
    try:
        balances = await exchange_manager.fetch_all_balances()
        return { "balances": balances }
    except Exception as e:
        logger.error(f"Error getting account balances: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

# Position and Trade Endpoints
@router.get("/exchange/positions")
async def get_all_positions():
    """
    Get all open positions across all symbols.
    """
    try:
        logger.info("Fetching positions from exchange manager...")
        logger.info(f"Wallet address: {settings.HYPERLIQUID_WALLET_KEY}")
        logger.info(f"Testnet mode: {settings.HYPERLIQUID_TESTNET}")
        positions = await exchange_manager.fetch_positions()
        logger.info(f"Exchange manager returned {len(positions)} positions")
        return {
            "positions": [
                {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "size": float(pos.size),
                    "notional": float(pos.notional),
                    "entry_price": float(pos.entry_price),
                    "mark_price": float(pos.mark_price),
                    "pnl": float(pos.pnl),
                    "percentage": float(pos.percentage) if pos.percentage else None,
                    "contracts": float(pos.contracts) if pos.contracts else None
                }
                for pos in positions
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching positions: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.get("/exchange/positions/{symbol}")
async def get_position_for_symbol(symbol: str):
    """
    Get position information for a specific symbol.
    """
    try:
        # Format symbol if needed
        symbol_to_use = symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"
        
        positions = await exchange_manager.fetch_positions([symbol_to_use])
        
        if not positions:
            return {
                "symbol": symbol_to_use,
                "position": None,
                "message": "No open position found for this symbol"
            }
        
        # Should only be one position for the symbol
        pos = positions[0]
        return {
            "symbol": symbol_to_use,
            "position": {
                "side": pos.side,
                "size": float(pos.size),
                "notional": float(pos.notional),
                "entry_price": float(pos.entry_price),
                "mark_price": float(pos.mark_price),
                "pnl": float(pos.pnl),
                "percentage": float(pos.percentage) if pos.percentage else None,
                "contracts": float(pos.contracts) if pos.contracts else None
            }
        }
    except Exception as e:
        logger.error(f"Error fetching position for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.get("/exchange/position-summary")
async def get_position_summary():
    """
    Get a comprehensive summary of all positions with totals and metrics.
    """
    try:
        summary = await exchange_manager.get_position_summary()
        return summary
    except Exception as e:
        logger.error(f"Error generating position summary: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.get("/exchange/open-orders")
async def get_open_orders(symbol: Optional[str] = None):
    """
    Get all open orders, optionally filtered by symbol.
    """
    try:
        # Format symbol if provided
        symbol_to_use = None
        if symbol:
            symbol_to_use = symbol
            if "/" in symbol_to_use and ":" not in symbol_to_use:
                parts = symbol_to_use.split("/")
                if len(parts) == 2 and parts[1] == "USDC":
                    symbol_to_use = f"{parts[0]}/USDC:USDC"
        
        orders = await exchange_manager.fetch_open_orders(symbol_to_use)
        return {
            "open_orders": [
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "type": order.type,
                    "side": order.side,
                    "amount": float(order.amount),
                    "price": float(order.price) if order.price else None,
                    "filled": float(order.filled),
                    "remaining": float(order.remaining),
                    "status": order.status,
                    "timestamp": order.timestamp,
                    "datetime": order.datetime
                }
                for order in orders
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching open orders: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.get("/exchange/trades")
async def get_recent_trades(
    symbol: Optional[str] = None,
    limit: Optional[int] = 50,
    hours_back: Optional[int] = 24
):
    """
    Get recent trades (fills) for the account.
    
    Args:
        symbol: Optional symbol to filter trades
        limit: Maximum number of trades to return (default: 50)
        hours_back: How many hours back to fetch trades (default: 24)
    """
    try:
        # Format symbol if provided
        symbol_to_use = None
        if symbol:
            symbol_to_use = symbol
            if "/" in symbol_to_use and ":" not in symbol_to_use:
                parts = symbol_to_use.split("/")
                if len(parts) == 2 and parts[1] == "USDC":
                    symbol_to_use = f"{parts[0]}/USDC:USDC"
        
        # Calculate timestamp for hours_back
        import time
        since = int((time.time() - (hours_back * 3600)) * 1000) if hours_back else None
        
        trades = await exchange_manager.fetch_my_trades(symbol_to_use, since, limit)
        return {
            "trades": [
                {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "amount": float(trade.amount),
                    "price": float(trade.price),
                    "cost": float(trade.cost),
                    "fee": float(trade.fee) if trade.fee else None,
                    "timestamp": trade.timestamp,
                    "datetime": trade.datetime
                }
                for trade in trades
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching trades: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service error: {str(e)}")

@router.post("/sync/positions")
async def sync_positions_to_database(db: AsyncSession = Depends(get_db_session)):
    """
    Sync existing HyperLiquid positions to database as trading plans.
    Creates TradingPlan records for positions that don't exist in the database.
    """
    try:
        logger.info("Starting position sync from HyperLiquid to database...")
        
        # Fetch raw positions from HyperLiquid to get leverage info
        params = {'user': settings.HYPERLIQUID_WALLET_KEY}
        raw_positions = await exchange_manager.exchange.fetch_positions(params=params)
        logger.info(f"Found {len(raw_positions)} raw positions in HyperLiquid")
        
        # Filter to only non-zero positions
        active_positions = []
        for pos in raw_positions:
            contracts = pos.get('contracts', 0)
            if contracts and contracts != 0:
                active_positions.append(pos)
        
        logger.info(f"Found {len(active_positions)} active positions")
        
        # Get existing trading plans from database
        result = await db.execute(select(TradingPlan))
        existing_plans = result.scalars().all()
        existing_symbols = {plan.symbol for plan in existing_plans}
        logger.info(f"Found {len(existing_symbols)} existing trading plans: {existing_symbols}")
        
        synced_count = 0
        skipped_count = 0
        
        for pos in active_positions:
            symbol = pos['symbol']
            
            if symbol in existing_symbols:
                logger.info(f"Skipping {symbol} - already exists in database")
                skipped_count += 1
                continue
                
            logger.info(f"Creating new trading plan for {symbol}")
            
            # Get leverage from raw position data
            leverage = pos.get('leverage', 1)
            if isinstance(leverage, (int, float)):
                leverage_val = int(leverage)
            else:
                leverage_val = 1
                
            # Calculate required margin from position data
            notional = float(pos.get('notional', 0))
            required_margin = notional / leverage_val if leverage_val > 0 else notional
            
            # Create SystemState object from position data
            entry_price = float(pos.get('entryPrice', 0))
            mark_price = float(pos.get('markPrice', 0)) if pos.get('markPrice') else entry_price
            side = pos.get('side', 'long')
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))
            
            system_state = SystemState(
                symbol=symbol,
                is_active=True,
                current_price=Decimal(str(mark_price)),
                entry_price=Decimal(str(entry_price)),
                unit_value=Decimal(str(required_margin * 0.05)),  # 5% units
                current_unit=0,  # We'll set this based on the position
                leverage=leverage_val,
                required_margin=Decimal(str(required_margin)),
                current_phase="advance",  # Default phase
                
                # Calculate allocations based on position
                long_invested=Decimal(str(notional)) if side == 'long' else Decimal("0.0"),
                long_cash=Decimal("0.0"),
                hedge_long=Decimal(str(notional)) if side == 'long' else Decimal("0.0"),
                hedge_short=Decimal(str(abs(notional))) if side == 'short' else Decimal("0.0"),
                
                # PNL from position
                realized_pnl=Decimal("0.0"),  # We don't have historical realized PNL
                unrealized_pnl=Decimal(str(unrealized_pnl)),
            )
            
            # Create trading plan
            trading_plan = TradingPlan(
                symbol=symbol,
                system_state=system_state.model_dump_json_safe(),
                initial_margin=required_margin,
                leverage=leverage_val,
                current_phase="advance",
                is_active="active",
                notes=f"Synced from existing HyperLiquid position on {datetime.now().isoformat()}"
            )
            
            db.add(trading_plan)
            synced_count += 1
            logger.info(f"Added {symbol} to database sync queue")
        
        # Commit all new trading plans
        await db.commit()
        
        logger.info(f"Position sync complete: {synced_count} synced, {skipped_count} skipped")
        
        return {
            "success": True,
            "message": f"Synced {synced_count} positions to database",
            "synced_count": synced_count,
            "skipped_count": skipped_count,
            "total_positions": len(active_positions)
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error syncing positions: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Sync error: {str(e)}")

@router.post("/trading/run-logic/{symbol}")
async def run_trading_logic_single_position(symbol: str, db: AsyncSession = Depends(get_db_session)):
    """
    Run trading logic on a single position with detailed logging.
    """
    try:
        logger.info(f"Running trading logic for {symbol}...")
        
        # Get trading plan from database
        result = await db.execute(
            select(TradingPlan).where(TradingPlan.symbol == symbol, TradingPlan.is_active == "active")
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            return {
                "success": False,
                "message": f"No active trading plan found for {symbol}",
                "symbol": symbol
            }
        
        # Get current price
        try:
            price_info = await exchange_manager.get_current_price(symbol)
            current_price = price_info
            logger.info(f"Current price for {symbol}: ${current_price}")
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return {
                "success": False,
                "message": f"Failed to get current price: {str(e)}",
                "symbol": symbol
            }
        
        # Load SystemState from database
        system_state = SystemState(**trading_plan.system_state)
        
        logger.info(f"\n=== PROCESSING {symbol} ===")
        logger.info(f"Current Price: ${current_price}")
        logger.info(f"Entry Price: ${system_state.entry_price}")
        logger.info(f"Current Phase: {system_state.current_phase}")
        logger.info(f"Current Unit: {system_state.current_unit}")
        logger.info(f"Peak Unit: {system_state.peak_unit}")
        logger.info(f"Valley Unit: {system_state.valley_unit}")
        logger.info(f"Long Invested: ${system_state.long_invested}")
        logger.info(f"Long Cash: ${system_state.long_cash}")
        logger.info(f"Hedge Long: ${system_state.hedge_long}")
        logger.info(f"Hedge Short: ${system_state.hedge_short}")
        logger.info(f"Unrealized PNL: ${system_state.unrealized_pnl}")
        
        # Calculate new unit before running logic
        price_change = current_price - system_state.entry_price
        new_unit = int(price_change / system_state.unit_size)
        unit_changed = new_unit != system_state.current_unit
        
        if unit_changed:
            logger.info(f"🔄 UNIT TICK: {symbol} unit changing from {system_state.current_unit} to {new_unit}")
        else:
            logger.info(f"📊 {symbol} unit unchanged at {system_state.current_unit}")
        
        # Run trading logic
        from app.services.trading_logic import run_trading_logic_for_state
        updated_state = await run_trading_logic_for_state(system_state, current_price)
        
        # Log final state after logic execution
        logger.info(f"✅ POST-LOGIC STATE for {symbol}:")
        logger.info(f"   Phase: {updated_state.current_phase}")
        logger.info(f"   Unit: {updated_state.current_unit}")
        logger.info(f"   Peak: {updated_state.peak_unit} @ ${updated_state.peak_price}")
        logger.info(f"   Valley: {updated_state.valley_unit} @ ${updated_state.valley_price}")
        logger.info(f"   Long/Invested: ${updated_state.long_invested}")
        logger.info(f"   Long/Cash: ${updated_state.long_cash}")
        logger.info(f"   Hedge/Long: ${updated_state.hedge_long}")
        logger.info(f"   Hedge/Short: ${updated_state.hedge_short}")
        logger.info(f"   Unrealized PNL: ${updated_state.unrealized_pnl}")
        
        # Update database with new state
        trading_plan.system_state = updated_state.model_dump_json_safe()
        trading_plan.current_phase = updated_state.current_phase
        await db.commit()
        
        return {
            "success": True,
            "message": f"Processed trading logic for {symbol}",
            "symbol": symbol,
            "current_price": float(current_price),
            "unit_changed": unit_changed,
            "old_unit": system_state.current_unit,
            "new_unit": updated_state.current_unit,
            "phase": updated_state.current_phase,
            "peak_unit": updated_state.peak_unit,
            "valley_unit": updated_state.valley_unit,
            "long_invested": float(updated_state.long_invested),
            "long_cash": float(updated_state.long_cash),
            "hedge_long": float(updated_state.hedge_long),
            "hedge_short": float(updated_state.hedge_short),
            "unrealized_pnl": float(updated_state.unrealized_pnl)
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error running trading logic for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Trading logic error: {str(e)}")

@router.post("/trading/run-logic")
async def run_trading_logic_all_positions_batch(db: AsyncSession = Depends(get_db_session)):
    """
    Run trading logic on all active positions with detailed logging.
    Updates database with new states after applying trading logic.
    """
    try:
        logger.info("Starting trading logic execution for all active positions...")
        
        # Get all active trading plans from database
        result = await db.execute(
            select(TradingPlan).where(TradingPlan.is_active == "active")
        )
        trading_plans = result.scalars().all()
        logger.info(f"Found {len(trading_plans)} active trading plans")
        
        if not trading_plans:
            return {
                "success": True,
                "message": "No active trading plans found",
                "processed_count": 0,
                "results": []
            }
        
        # Get current prices for all symbols
        symbols = [plan.symbol for plan in trading_plans]
        current_prices = {}
        
        for symbol in symbols:
            try:
                price_info = await exchange_manager.get_current_price(symbol)
                current_prices[symbol] = price_info
                logger.info(f"Current price for {symbol}: ${price_info}")
            except Exception as e:
                logger.error(f"Failed to get price for {symbol}: {e}")
                continue
        
        processed_count = 0
        results = []
        
        # Process each trading plan
        for plan in trading_plans:
            symbol = plan.symbol
            
            if symbol not in current_prices:
                logger.warning(f"Skipping {symbol} - no current price available")
                continue
                
            try:
                # Load SystemState from database
                logger.info(f"Attempting to load SystemState for {symbol}...")
                logger.info(f"Raw system_state keys: {list(plan.system_state.keys())}")
                system_state = SystemState(**plan.system_state)
                current_price = current_prices[symbol]
                
                logger.info(f"\n=== PROCESSING {symbol} ===")
                logger.info(f"Current Price: ${current_price}")
                logger.info(f"Entry Price: ${system_state.entry_price}")
                logger.info(f"Current Phase: {system_state.current_phase}")
                logger.info(f"Current Unit: {system_state.current_unit}")
                logger.info(f"Peak Unit: {system_state.peak_unit}")
                logger.info(f"Valley Unit: {system_state.valley_unit}")
                logger.info(f"Long Invested: ${system_state.long_invested}")
                logger.info(f"Long Cash: ${system_state.long_cash}")
                logger.info(f"Hedge Long: ${system_state.hedge_long}")
                logger.info(f"Hedge Short: ${system_state.hedge_short}")
                logger.info(f"Unrealized PNL: ${system_state.unrealized_pnl}")
                
                # Calculate new unit before running logic
                price_change = current_price - system_state.entry_price
                new_unit = int(price_change / system_state.unit_size)
                unit_changed = new_unit != system_state.current_unit
                
                if unit_changed:
                    logger.info(f"🔄 UNIT TICK: {symbol} unit changing from {system_state.current_unit} to {new_unit}")
                else:
                    logger.info(f"📊 {symbol} unit unchanged at {system_state.current_unit}")
                
                # Run trading logic
                from app.services.trading_logic import run_trading_logic_for_state
                updated_state = await run_trading_logic_for_state(system_state, current_price)
                
                # Log final state after logic execution
                logger.info(f"✅ POST-LOGIC STATE for {symbol}:")
                logger.info(f"   Phase: {updated_state.current_phase}")
                logger.info(f"   Unit: {updated_state.current_unit}")
                logger.info(f"   Peak: {updated_state.peak_unit} @ ${updated_state.peak_price}")
                logger.info(f"   Valley: {updated_state.valley_unit} @ ${updated_state.valley_price}")
                logger.info(f"   Long/Invested: ${updated_state.long_invested}")
                logger.info(f"   Long/Cash: ${updated_state.long_cash}")
                logger.info(f"   Hedge/Long: ${updated_state.hedge_long}")
                logger.info(f"   Hedge/Short: ${updated_state.hedge_short}")
                logger.info(f"   Unrealized PNL: ${updated_state.unrealized_pnl}")
                
                # Update database with new state
                plan.system_state = updated_state.model_dump_json_safe()
                plan.current_phase = updated_state.current_phase
                
                processed_count += 1
                
                results.append({
                    "symbol": symbol,
                    "current_price": float(current_price),
                    "unit_changed": unit_changed,
                    "old_unit": system_state.current_unit,
                    "new_unit": updated_state.current_unit,
                    "phase": updated_state.current_phase,
                    "peak_unit": updated_state.peak_unit,
                    "valley_unit": updated_state.valley_unit,
                    "long_invested": float(updated_state.long_invested),
                    "long_cash": float(updated_state.long_cash),
                    "hedge_long": float(updated_state.hedge_long),
                    "hedge_short": float(updated_state.hedge_short),
                    "unrealized_pnl": float(updated_state.unrealized_pnl)
                })
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}", exc_info=True)
                results.append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        # Commit all updates
        await db.commit()
        logger.info(f"Trading logic execution complete. Processed {processed_count} positions.")
        
        return {
            "success": True,
            "message": f"Processed {processed_count} trading positions",
            "processed_count": processed_count,
            "results": results
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error running trading logic: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Trading logic error: {str(e)}")

@router.get("/trading/plans")
async def get_all_trading_plans(db: AsyncSession = Depends(get_db_session)):
    """
    Get all trading plans from database for debugging.
    """
    try:
        result = await db.execute(select(TradingPlan))
        trading_plans = result.scalars().all()
        
        plans_data = []
        for plan in trading_plans:
            plans_data.append({
                "id": plan.id,
                "symbol": plan.symbol,
                "is_active": plan.is_active,
                "current_phase": plan.current_phase,
                "leverage": plan.leverage,
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
                "system_state_keys": list(plan.system_state.keys()) if plan.system_state else []
            })
        
        return {
            "total_plans": len(trading_plans),
            "plans": plans_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching trading plans: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")

@router.post("/trade/close/{symbol}")
async def close_position(symbol: str, db: AsyncSession = Depends(get_db_session)):
    """
    Close an open position by selling all contracts.
    """
    try:
        logger.info(f"Closing position for {symbol}...")
        
        # Get current positions to find the one to close
        positions = await exchange_manager.fetch_positions()
        target_position = None
        
        for pos in positions:
            if pos.symbol == symbol:
                target_position = pos
                break
        
        if not target_position:
            return {
                "success": False,
                "message": f"No open position found for {symbol}"
            }
        
        if target_position.contracts <= 0:
            return {
                "success": False,
                "message": f"Position for {symbol} has no contracts to close"
            }
        
        # Place sell order to close the position
        logger.info(f"Closing {target_position.contracts} contracts for {symbol}")
        
        order_result = await exchange_manager.place_order(
            symbol=symbol,
            order_type="market",
            side="sell",
            amount=float(target_position.contracts),
            params={"reduceOnly": True}
        )
        
        if order_result.success:
            # Mark trading plan as inactive in database
            result = await db.execute(
                select(TradingPlan).where(TradingPlan.symbol == symbol, TradingPlan.is_active == "active")
            )
            trading_plan = result.scalar_one_or_none()
            
            if trading_plan:
                trading_plan.is_active = "closed"
                trading_plan.notes = f"Position closed manually on {datetime.now().isoformat()}"
                await db.commit()
                logger.info(f"Marked trading plan {trading_plan.id} as closed")
            
            return {
                "success": True,
                "message": f"Successfully closed position for {symbol}",
                "symbol": symbol,
                "contracts_closed": float(target_position.contracts),
                "order_id": order_result.order_id,
                "pnl": float(target_position.pnl)
            }
        else:
            return {
                "success": False,
                "message": f"Failed to close position: {order_result.error_message}",
                "symbol": symbol
            }
            
    except Exception as e:
        logger.error(f"Error closing position for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Close position error: {str(e)}")


@router.delete("/plans/{plan_id}")
async def delete_trading_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a trading plan by ID."""
    try:
        result = await db.execute(
            select(TradingPlan).where(TradingPlan.id == plan_id)
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            raise HTTPException(status_code=404, detail="Trading plan not found")
        
        await db.delete(trading_plan)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Trading plan {plan_id} deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error deleting trading plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")


@router.post("/sync-positions")
async def sync_positions_with_exchange(db: AsyncSession = Depends(get_db)):
    """
    Sync trading plans with actual exchange positions.
    Close plans for positions that no longer exist, and detect orphaned positions.
    """
    try:
        # Get all active trading plans
        result = await db.execute(
            select(TradingPlan).where(TradingPlan.is_active == "active")
        )
        active_plans = result.scalars().all()
        
        # Get all current positions from exchange
        positions = await exchange_manager.get_positions()
        position_symbols = {pos.symbol for pos in positions if pos.size != 0}
        
        sync_results = {
            "plans_closed": [],
            "orphaned_positions": [],
            "active_matches": []
        }
        
        # Check each active plan against actual positions
        for plan in active_plans:
            if plan.symbol not in position_symbols:
                # Plan exists but no position - close the plan
                plan.is_active = "closed"
                plan.notes = f"Auto-closed: No position found on exchange at {datetime.now().isoformat()}"
                sync_results["plans_closed"].append({
                    "id": plan.id,
                    "symbol": plan.symbol,
                    "reason": "No exchange position"
                })
            else:
                sync_results["active_matches"].append(plan.symbol)
        
        # Check for positions without plans (orphaned positions)
        plan_symbols = {plan.symbol for plan in active_plans}
        for symbol in position_symbols:
            if symbol not in plan_symbols:
                sync_results["orphaned_positions"].append(symbol)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Position sync completed",
            "results": sync_results
        }
        
    except Exception as e:
        logger.error(f"Error syncing positions: {e}")
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")


@router.post("/recover-state")
async def recover_trading_state(db: AsyncSession = Depends(get_db)):
    """
    Attempt to recover trading state after a crash by syncing with exchange positions
    and cleaning up corrupted database entries.
    """
    try:
        recovery_results = {
            "cleaned_plans": [],
            "recovered_positions": [],
            "errors": []
        }
        
        # First, clean up duplicate plans for the same symbol
        result = await db.execute(
            select(TradingPlan.symbol, func.count(TradingPlan.id).label('count'))
            .where(TradingPlan.is_active == "active")
            .group_by(TradingPlan.symbol)
            .having(func.count(TradingPlan.id) > 1)
        )
        duplicates = result.all()
        
        for symbol, count in duplicates:
            # Get all plans for this symbol
            dup_result = await db.execute(
                select(TradingPlan)
                .where(TradingPlan.symbol == symbol, TradingPlan.is_active == "active")
                .order_by(TradingPlan.created_at.desc())
            )
            dup_plans = dup_result.scalars().all()
            
            # Keep the most recent one, delete the rest
            for plan in dup_plans[1:]:
                await db.delete(plan)
                recovery_results["cleaned_plans"].append({
                    "id": plan.id,
                    "symbol": symbol,
                    "reason": "Duplicate plan removed"
                })
        
        await db.commit()
        
        # Now sync with exchange positions
        sync_response = await sync_positions_with_exchange(db)
        recovery_results["sync_results"] = sync_response["results"]
        
        return {
            "success": True,
            "message": "State recovery completed",
            "results": recovery_results
        }
        
    except Exception as e:
        logger.error(f"Error recovering state: {e}")
        raise HTTPException(status_code=500, detail=f"Recovery error: {str(e)}")
