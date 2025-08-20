# backend/app/api/websockets.py

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.models.state import SystemState
from app.schemas.plan import TradingPlan
from app.services.exchange import ExchangeManager
from app.services.trading_logic import on_unit_change
from sqlalchemy.future import select

router = APIRouter()
exchange_manager = ExchangeManager()

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.active_connections:
            self.active_connections[symbol] = []
        self.active_connections[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket, symbol: str):
        self.active_connections[symbol].remove(websocket)

    async def broadcast(self, message: dict, symbol: str):
        for connection in self.active_connections.get(symbol, []):
            await connection.send_json(message)

manager = ConnectionManager()

async def trading_loop(symbol: str, db: AsyncSession):
    """
    The main trading loop for a single symbol.
    This would run as a background task.
    """
    # Load the initial state from the database
    result = await db.execute(select(TradingPlan).where(TradingPlan.symbol == symbol))
    plan = result.scalar_one_or_none()
    
    if not plan:
        print(f"No active plan for {symbol}. Stopping loop.")
        return

    current_state = SystemState(**plan.state)

    while True:
        try:
            # In a real application, this would listen to a live WebSocket feed from the exchange.
            # For this example, we simulate it by fetching the price every few seconds.
            await asyncio.sleep(5) 
            
            current_price = await exchange_manager.get_current_price(symbol)
            
            updated_state = await on_unit_change(current_state, current_price, exchange_manager)
            
            # If the state has changed, persist and broadcast it
            if updated_state != current_state:
                plan.state = updated_state.dict()
                await db.commit()
                await manager.broadcast(updated_state.dict(), symbol)
                current_state = updated_state

        except Exception as e:
            print(f"Error in trading loop for {symbol}: {e}")
            # Add more robust error handling/reconnection logic here
            await asyncio.sleep(10)


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str, db: AsyncSession = Depends(get_db_session)):
    await manager.connect(websocket, symbol)
    
    # Start the trading loop as a background task if it's not already running for this symbol.
    # A more robust solution would use a task manager like Celery or FastAPI's BackgroundTasks.
    # For simplicity, we'll just check if a task is running. This part is conceptual.
    # if not is_task_running(symbol):
    #    asyncio.create_task(trading_loop(symbol, db))
    
    # For this example, we'll just start it. In a real app, you need to prevent multiple loops.
    asyncio.create_task(trading_loop(symbol, db))

    try:
        while True:
            # Keep the connection alive, listening for any client messages (optional)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, symbol)
        print(f"Client disconnected from {symbol} feed.")