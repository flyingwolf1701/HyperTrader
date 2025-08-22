from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete
from typing import List, Optional
import logging
from decimal import Decimal
import json

from app.db.session import get_db_session
from app.models.state import SystemState, TradingPlanCreate, TradingPlanUpdate
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
        unit_value = (required_margin * Decimal("0.05")) / plan_data.leverage
        
        system_state = SystemState(
            symbol=symbol_to_use,
            entry_price=entry_price,
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
            system_state=system_state.dict(),
            initial_margin=float(required_margin),
            leverage=plan_data.leverage,
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
        positions = await exchange_manager.fetch_positions()
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
