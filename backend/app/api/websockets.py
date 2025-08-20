from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import asyncio
import json
import logging
from typing import Dict, List, Set
from decimal import Decimal
import ccxt.pro as ccxt

from app.db.session import get_db_session
from app.models.state import SystemState
from app.schemas import TradingPlan
from app.services.exchange import exchange_manager
from app.services.trading_logic import trading_logic
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.active_connections:
            self.active_connections[symbol] = []
        self.active_connections[symbol].append(websocket)
        logger.info(f"Client connected to {symbol} feed")
    
    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.active_connections:
            if websocket in self.active_connections[symbol]:
                self.active_connections[symbol].remove(websocket)
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]
        logger.info(f"Client disconnected from {symbol} feed")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_symbol(self, message: str, symbol: str):
        if symbol in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[symbol]:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {symbol}: {e}")
                    disconnected.append(websocket)
            
            # Clean up disconnected clients
            for ws in disconnected:
                self.disconnect(ws, symbol)


# Global connection manager
manager = ConnectionManager()

# Track active trading loops
active_trading_loops: Dict[str, asyncio.Task] = {}


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time trading data and control.
    Clients connect here to receive live updates about trading state.
    """
    await manager.connect(websocket, symbol)
    
    try:
        while True:
            # Listen for client messages (control commands)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)
                
                await handle_client_message(message, symbol, websocket)
                
            except asyncio.TimeoutError:
                # No message received, continue loop
                continue
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({"error": "Invalid JSON format"}),
                    websocket
                )
            except Exception as e:
                logger.error(f"Error processing client message: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from {symbol}")
    except Exception as e:
        logger.error(f"WebSocket error for {symbol}: {e}")
    finally:
        manager.disconnect(websocket, symbol)


async def handle_client_message(message: dict, symbol: str, websocket: WebSocket):
    """Handle messages from WebSocket clients"""
    
    message_type = message.get("type")
    
    if message_type == "start_trading":
        # Start the trading loop for this symbol
        if symbol not in active_trading_loops:
            task = asyncio.create_task(trading_loop(symbol))
            active_trading_loops[symbol] = task
            await manager.send_personal_message(
                json.dumps({"type": "trading_started", "symbol": symbol}),
                websocket
            )
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": f"Trading already active for {symbol}"}),
                websocket
            )
    
    elif message_type == "stop_trading":
        # Stop the trading loop for this symbol
        if symbol in active_trading_loops:
            active_trading_loops[symbol].cancel()
            del active_trading_loops[symbol]
            await manager.send_personal_message(
                json.dumps({"type": "trading_stopped", "symbol": symbol}),
                websocket
            )
        else:
            await manager.send_personal_message(
                json.dumps({"type": "error", "message": f"No active trading for {symbol}"}),
                websocket
            )
    
    elif message_type == "get_status":
        # Send current trading status
        is_active = symbol in active_trading_loops
        await manager.send_personal_message(
            json.dumps({
                "type": "status_response",
                "symbol": symbol,
                "trading_active": is_active
            }),
            websocket
        )
    
    else:
        await manager.send_personal_message(
            json.dumps({"type": "error", "message": f"Unknown message type: {message_type}"}),
            websocket
        )


async def trading_loop(symbol: str):
    """
    Main trading loop that monitors price changes and executes trading logic.
    This is the heart of the real-time trading system.
    """
    logger.info(f"Starting trading loop for {symbol}")
    
    exchange = None
    db_session = None
    
    try:
        # Initialize exchange WebSocket connection
        exchange = ccxt.hyperliquid({
            'apiKey': settings.HYPERLIQUID_API_KEY,
            'secret': settings.HYPERLIQUID_SECRET_KEY,
            'sandbox': settings.HYPERLIQUID_TESTNET,
            'options': {'defaultType': 'swap'}
        })
        
        # Get database session
        from app.db.session import async_session_maker
        db_session = async_session_maker()
        
        # Get current trading plan
        result = await db_session.execute(
            select(TradingPlan).where(
                TradingPlan.symbol == symbol,
                TradingPlan.is_active == "active"
            ).order_by(TradingPlan.created_at.desc())
        )
        trading_plan = result.scalar_one_or_none()
        
        if not trading_plan:
            logger.error(f"No active trading plan found for {symbol}")
            return
        
        # Parse current system state
        current_state = SystemState(**trading_plan.system_state)
        last_unit = current_state.current_unit
        
        logger.info(f"Trading loop initialized for {symbol}. Current unit: {last_unit}")
        
        # Main price monitoring loop
        while True:
            try:
                # Get current ticker/price
                ticker = await exchange.fetch_ticker(symbol)
                current_price = Decimal(str(ticker['last']))
                
                # Calculate current unit
                if current_state.unit_value > 0:
                    price_diff = current_price - current_state.entry_price
                    current_unit = int(price_diff / current_state.unit_value)
                else:
                    current_unit = 0
                
                # Check if unit has changed (only act on whole unit changes)
                if current_unit != last_unit:
                    logger.info(f"{symbol}: Unit change {last_unit} -> {current_unit} at price ${current_price}")
                    
                    try:
                        # Call trading logic
                        updated_state = await trading_logic.on_unit_change(
                            current_state, current_unit, current_price
                        )
                        
                        # Update database with new state
                        await db_session.execute(
                            update(TradingPlan)
                            .where(TradingPlan.id == trading_plan.id)
                            .values(
                                system_state=updated_state.dict(),
                                current_phase=updated_state.current_phase
                            )
                        )
                        await db_session.commit()
                        
                        # Broadcast updated state to all connected clients
                        state_update = {
                            "type": "state_update",
                            "symbol": symbol,
                            "current_price": float(current_price),
                            "unit_change": {
                                "from": last_unit,
                                "to": current_unit
                            },
                            "system_state": {
                                "current_phase": updated_state.current_phase,
                                "current_unit": updated_state.current_unit,
                                "peak_unit": updated_state.peak_unit,
                                "valley_unit": updated_state.valley_unit,
                                "long_invested": float(updated_state.long_invested),
                                "long_cash": float(updated_state.long_cash),
                                "hedge_long": float(updated_state.hedge_long),
                                "hedge_short": float(updated_state.hedge_short),
                                "total_value": float(updated_state.get_total_portfolio_value()),
                                "long_allocation_percent": float(updated_state.get_long_allocation_percent()),
                                "hedge_allocation_percent": float(updated_state.get_hedge_allocation_percent()),
                                "choppy_trading": updated_state.is_choppy_trading_active(),
                                "reset_ready": updated_state.is_reset_condition_met()
                            },
                            "timestamp": ticker.get('timestamp')
                        }
                        
                        await manager.broadcast_to_symbol(
                            json.dumps(state_update), symbol
                        )
                        
                        # Update local state
                        current_state = updated_state
                        last_unit = current_unit
                        
                    except Exception as e:
                        logger.error(f"Error in trading logic for {symbol}: {e}")
                        # Send error to clients but continue loop
                        error_message = {
                            "type": "trading_error",
                            "symbol": symbol,
                            "error": str(e),
                            "current_price": float(current_price)
                        }
                        await manager.broadcast_to_symbol(
                            json.dumps(error_message), symbol
                        )
                
                else:
                    # No unit change, just send price update
                    price_update = {
                        "type": "price_update",
                        "symbol": symbol,
                        "price": float(current_price),
                        "current_unit": current_unit,
                        "timestamp": ticker.get('timestamp')
                    }
                    await manager.broadcast_to_symbol(
                        json.dumps(price_update), symbol
                    )
                
                # Wait before next iteration
                await asyncio.sleep(1)  # Check price every second
                
            except Exception as e:
                logger.error(f"Error in price monitoring loop for {symbol}: {e}")
                await asyncio.sleep(5)  # Wait longer on error
                
    except asyncio.CancelledError:
        logger.info(f"Trading loop cancelled for {symbol}")
        raise
    except Exception as e:
        logger.error(f"Fatal error in trading loop for {symbol}: {e}")
    finally:
        # Cleanup
        if exchange:
            await exchange.close()
        if db_session:
            await db_session.close()
        
        # Notify clients that trading has stopped
        stop_message = {
            "type": "trading_stopped",
            "symbol": symbol,
            "reason": "Loop ended"
        }
        await manager.broadcast_to_symbol(json.dumps(stop_message), symbol)
        
        # Remove from active loops
        if symbol in active_trading_loops:
            del active_trading_loops[symbol]
        
        logger.info(f"Trading loop ended for {symbol}")


@router.get("/trading/status/{symbol}")
async def get_trading_status(symbol: str):
    """Get current trading status for a symbol"""
    is_active = symbol in active_trading_loops
    return {
        "symbol": symbol,
        "trading_active": is_active,
        "connected_clients": len(manager.active_connections.get(symbol, []))
    }


@router.post("/trading/start/{symbol}")
async def start_trading_via_rest(symbol: str):
    """Start trading for a symbol via REST API"""
    if symbol not in active_trading_loops:
        task = asyncio.create_task(trading_loop(symbol))
        active_trading_loops[symbol] = task
        return {"success": True, "message": f"Trading started for {symbol}"}
    else:
        return {"success": False, "message": f"Trading already active for {symbol}"}


@router.post("/trading/stop/{symbol}")
async def stop_trading_via_rest(symbol: str):
    """Stop trading for a symbol via REST API"""
    if symbol in active_trading_loops:
        active_trading_loops[symbol].cancel()
        del active_trading_loops[symbol]
        return {"success": True, "message": f"Trading stopped for {symbol}"}
    else:
        return {"success": False, "message": f"No active trading for {symbol}"}