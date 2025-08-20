# backend/app/api/endpoints.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from typing import List

from app.db.session import get_db_session
from app.models.state import SystemState
from app.schemas.plan import TradingPlan
from app.services.exchange import ExchangeManager
from app.services.trading_logic import calculate_unit_value

# In a real application, you would have a more robust way to manage service instances
# For simplicity, we'll instantiate it here.
exchange_manager = ExchangeManager()

router = APIRouter()

class TradeStartRequest(BaseModel):
    """Pydantic model for the request to start a new trade."""
    symbol: str
    margin: float
    leverage: int

@router.post("/trade/start")
async def start_trade(
    request: TradeStartRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initializes a new trading plan.
    This is a simplified version; a real implementation would place an order first
    to get the true entry price before creating the state.
    """
    # For this example, we'll simulate the entry
    entry_price = await exchange_manager.get_current_price(request.symbol)
    initial_margin = Decimal(str(request.margin))
    
    # Create the initial state
    initial_state = SystemState(
        symbol=request.symbol,
        current_phase='advance',
        entry_price=entry_price,
        unit_value=calculate_unit_value(entry_price, request.leverage),
        long_invested=initial_margin / Decimal(2),
        long_cash=Decimal(0),
        hedge_long=initial_margin / Decimal(2),
        hedge_short=Decimal(0),
        initial_margin=initial_margin,
        current_unit=0,
        peak_unit=0,
        peak_price=entry_price
    )

    # Persist the new trading plan to the database
    new_plan = TradingPlan(
        symbol=request.symbol,
        state=initial_state.dict()
    )
    db.add(new_plan)
    await db.commit()

    return {"message": "Trade plan initiated successfully", "initial_state": initial_state}


@router.get("/exchange/pairs")
async def get_exchange_pairs():
    """
    Fetches all available trading pairs from the exchange.
    """
    try:
        markets = await exchange_manager.fetch_markets()
        # We only need the symbol names for the frontend
        pairs = [market['symbol'] for market in markets.values()]
        # Here you could add logic to categorize by L1, etc.
        return {"pairs": pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Additional endpoints for favorites would be added here
# GET /user/favorites
# POST /user/favorites