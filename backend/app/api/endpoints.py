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
from app.services.trading_logic import trading_logic

logger = logging.getLogger(__name__)

router = APIRouter()


# Trading Plan Endpoints
@router.post("/trade/start", response_model=dict)
async def start_trading_plan(
    plan_data: TradingPlanCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Start a new trading plan by placing initial order and creating SystemState
    """
    try:
        # Validate market is available
        if not exchange_manager.is_market_available(plan_data.symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Market {plan_data.symbol} is not available"
            )
        
        # Get current price
        current_price = await exchange_manager.get_current_price(plan_data.symbol)
        if current_price is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to get current price for {plan_data.symbol}"
            )
        
        # Calculate position size and place initial order
        total_position_value = plan_data.initial_margin * plan_data.leverage
        position_size = total_position_value / current_price
        
        # Place initial buy order
        order_result = await exchange_manager.place_order(
            symbol=plan_data.symbol,
            order_type="market",
            side="buy",
            amount=position_size
        )
        
        if not order_result.success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to place initial order: {order_result.error_message}"
            )
        
        # Use actual fill price and cost
        entry_price = order_result.average_price or current_price
        actual_cost = order_result.cost or total_position_value
        
        # Calculate unit value (5% of margin with leverage factor)
        unit_value = (plan_data.initial_margin * Decimal("0.05")) / plan_data.leverage
        
        # Create SystemState
        system_state = SystemState(
            symbol=plan_data.symbol,
            entry_price=entry_price,
            unit_value=unit_value,
            initial_margin=plan_data.initial_margin,
            leverage=plan_data.leverage,
            # Split initial margin 50/50 between allocations
            long_invested=actual_cost / 2,
            long_cash=Decimal("0"),
            hedge_long=actual_cost / 2,
            hedge_short=Decimal("0")
        )
        
        # Save to database
        trading_plan = TradingPlan(
            symbol=plan_data.symbol,
            system_state=system_state.dict(),
            initial_margin=plan_data.initial_margin,
            leverage=plan_data.leverage,
            current_phase=system_state.current_phase
        )
        
        db.add(trading_plan)
        await db.commit()
        await db.refresh(trading_plan)
        
        logger.info(f"Started new trading plan for {plan_data.symbol} with ID {trading_plan.id}")
        
        return {
            "success": True,
            "plan_id": trading_plan.id,
            "symbol": plan_data.symbol,
            "entry_price": float(entry_price),
            "initial_margin": float(plan_data.initial_margin),
            "order_id": order_result.order_id,
            "system_state": system_state.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting trading plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/trade/state/{symbol}", response_model=dict)
async def get_trading_state(
    symbol: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get current trading state for a symbol"""
    try:
        # Query for active trading plan
        result = await db.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active trading plan found for {symbol}"
            )
        
        # Parse system state
        system_state = SystemState(**trading_plan.system_state)
        
        # Get current market price
        current_price = await exchange_manager.get_current_price(symbol)
        
        # Calculate unrealized PnL
        if current_price:
            # Simple PnL calculation - this could be more sophisticated
            price_change = current_price - system_state.entry_price
            position_value = system_state.long_invested + system_state.hedge_long
            unrealized_pnl = (price_change / system_state.entry_price) * position_value
            system_state.unrealized_pnl = unrealized_pnl
        
        return {
            "plan_id": trading_plan.id,
            "system_state": system_state.dict(),
            "current_price": float(current_price) if current_price else None,
            "created_at": trading_plan.created_at.isoformat(),
            "updated_at": trading_plan.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trading state for {symbol}: {e}")
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
    """Update trading state (used by WebSocket handler)"""
    try:
        # Get current trading plan
        result = await db.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active trading plan found for {symbol}"
            )
        
        # Update system state
        system_state_dict = trading_plan.system_state.copy()
        
        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                system_state_dict[field] = value
        
        # Update database record
        await db.execute(
            update(TradingPlan)
            .where(TradingPlan.id == trading_plan.id)
            .values(
                system_state=system_state_dict,
                current_phase=system_state_dict.get('current_phase', trading_plan.current_phase)
            )
        )
        await db.commit()
        
        return {"success": True, "updated_fields": list(update_data.dict(exclude_unset=True).keys())}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating trading state for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


# Exchange Endpoints
@router.get("/exchange/pairs", response_model=List[dict])
async def get_exchange_pairs():
    """Get all available trading pairs from the exchange"""
    try:
        markets = await exchange_manager.fetch_markets()
        
        pairs = []
        for market in markets:
            if market.active:  # Only return active markets
                pairs.append({
                    "symbol": market.symbol,
                    "base": market.base,
                    "quote": market.quote,
                    "min_amount": float(market.min_amount) if market.min_amount else None,
                    "max_amount": float(market.max_amount) if market.max_amount else None,
                    "min_price": float(market.min_price) if market.min_price else None,
                    "max_price": float(market.max_price) if market.max_price else None,
                })
        
        return pairs
        
    except Exception as e:
        logger.error(f"Error fetching exchange pairs: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to fetch market data: {str(e)}"
        )


@router.get("/exchange/price/{symbol}")
async def get_current_price(symbol: str):
    """Get current price for a symbol"""
    try:
        price = await exchange_manager.get_current_price(symbol)
        
        if price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to get price for {symbol}"
            )
        
        return {
            "symbol": symbol,
            "price": float(price),
            "timestamp": None  # Could add timestamp from ticker data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error: {str(e)}"
        )


# User Favorites Endpoints
@router.get("/user/favorites", response_model=List[dict])
async def get_user_favorites(
    user_id: str = "default_user",
    db: AsyncSession = Depends(get_db_session)
):
    """Get user's favorite trading pairs"""
    try:
        result = await db.execute(
            select(UserFavorite)
            .where(
                UserFavorite.user_id == user_id,
                UserFavorite.is_active == True
            )
            .order_by(UserFavorite.sort_order.asc(), UserFavorite.created_at.asc())
        )
        favorites = result.scalars().all()
        
        favorites_list = []
        for fav in favorites:
            # Get current price if possible
            current_price = await exchange_manager.get_current_price(fav.symbol)
            
            favorites_list.append({
                "id": fav.id,
                "symbol": fav.symbol,
                "base_asset": fav.base_asset,
                "quote_asset": fav.quote_asset,
                "exchange": fav.exchange,
                "sort_order": fav.sort_order,
                "notes": fav.notes,
                "tags": fav.tags.split(",") if fav.tags else [],
                "current_price": float(current_price) if current_price else None,
                "created_at": fav.created_at.isoformat()
            })
        
        return favorites_list
        
    except Exception as e:
        logger.error(f"Error getting user favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.post("/user/favorites", response_model=dict)
async def add_user_favorite(
    symbol: str,
    user_id: str = "default_user",
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Add a trading pair to user favorites"""
    try:
        # Check if symbol exists and is valid
        market = exchange_manager.get_market_info(symbol)
        if not market:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid trading pair: {symbol}"
            )
        
        # Check if already favorited
        existing = await db.execute(
            select(UserFavorite).where(
                UserFavorite.user_id == user_id,
                UserFavorite.symbol == symbol
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Symbol {symbol} is already in favorites"
            )
        
        # Create favorite
        favorite = UserFavorite(
            user_id=user_id,
            symbol=symbol,
            base_asset=market.base,
            quote_asset=market.quote,
            notes=notes,
            tags=",".join(tags) if tags else None
        )
        
        db.add(favorite)
        await db.commit()
        await db.refresh(favorite)
        
        return {
            "success": True,
            "id": favorite.id,
            "symbol": symbol,
            "message": f"Added {symbol} to favorites"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding favorite {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.delete("/user/favorites/{favorite_id}")
async def remove_user_favorite(
    favorite_id: int,
    user_id: str = "default_user",
    db: AsyncSession = Depends(get_db_session)
):
    """Remove a trading pair from user favorites"""
    try:
        # Find and delete favorite
        result = await db.execute(
            select(UserFavorite).where(
                UserFavorite.id == favorite_id,
                UserFavorite.user_id == user_id
            )
        )
        favorite = result.scalar_one_or_none()
        
        if not favorite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Favorite not found"
            )
        
        await db.delete(favorite)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Removed {favorite.symbol} from favorites"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing favorite {favorite_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )