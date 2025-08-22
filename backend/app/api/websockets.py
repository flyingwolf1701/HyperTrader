import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from decimal import Decimal

from app.db.session import get_db_session
from app.models.state import SystemState
from app.schemas import TradingPlan
from app.services.exchange import exchange_manager
# Import the new function from trading_logic
from app.services.trading_logic import run_trading_logic_for_state

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/{symbol}")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    db: AsyncSession = Depends(get_db_session)
):
    await websocket.accept()
    logger.info(f"WebSocket connection established for {symbol}")

    try:
        # 1. Fetch the initial trading plan state from the database
        result = await db.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()

        if not trading_plan:
            await websocket.send_json({"error": f"No active trading plan for {symbol}"})
            await websocket.close()
            return

        # 2. Deserialize the database JSON into our Pydantic SystemState model
        system_state = SystemState(**trading_plan.system_state)

        # 3. Start the main trading loop
        while True:
            # Get the latest price from the exchange
            current_price = await exchange_manager.get_current_price(symbol)
            if current_price is None:
                logger.warning(f"Could not retrieve price for {symbol}, skipping cycle.")
                await asyncio.sleep(5) # Wait before retrying
                continue

            # 4. Run the trading logic with the current state and price
            # This returns the updated state object
            system_state = await run_trading_logic_for_state(system_state, current_price)

            # 5. Send the updated state to the client
            # Convert Decimal to string for JSON serialization
            state_dict = system_state.dict()
            for key, value in state_dict.items():
                if isinstance(value, Decimal):
                    state_dict[key] = str(value)

            await websocket.send_json({
                "type": "state_update",
                "data": state_dict
            })

            # 6. Persist the updated state back to the database
            await db.execute(
                update(TradingPlan)
                .where(TradingPlan.id == trading_plan.id)
                .values(
                    system_state=system_state.dict(),
                    current_phase=system_state.current_phase
                )
            )
            await db.commit()

            # Wait for the next cycle
            await asyncio.sleep(10) # Adjust interval as needed

    except WebSocketDisconnect:
        logger.info(f"WebSocket for {symbol} disconnected.")
    except Exception as e:
        logger.error(f"Error in WebSocket for {symbol}: {e}", exc_info=True)
        # Try to send an error message before closing
        try:
            await websocket.send_json({"error": "An internal error occurred."})
        except Exception:
            pass # Connection might already be closed
        await websocket.close(code=1011, reason="Internal Server Error")

