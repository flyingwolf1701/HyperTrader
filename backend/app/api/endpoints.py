from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict
import logging
from decimal import Decimal
import json
import os
from datetime import datetime

from app.core.config import settings
from app.services.exchange import exchange_manager, MarketInfo
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for API requests
class OrderRequest(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    type: str  # 'market' or 'limit'
    price: Optional[float] = None

class StrategyStartRequest(BaseModel):
    symbol: str
    position_size_usd: float
    unit_size: float
    leverage: int = 1

# Strategy state management with multi-symbol support
STRATEGY_STATE_DIR = "strategies"

def get_strategy_filename(symbol: str) -> str:
    """Get strategy filename for a symbol"""
    safe_symbol = symbol.replace("/", "_").replace(":", "_")
    return f"{STRATEGY_STATE_DIR}/strategy_{safe_symbol}.json"

def ensure_strategy_dir():
    """Ensure strategy directory exists"""
    if not os.path.exists(STRATEGY_STATE_DIR):
        os.makedirs(STRATEGY_STATE_DIR)
        logger.info(f"Created strategy directory: {STRATEGY_STATE_DIR}")

def load_strategy_state(symbol: Optional[str] = None):
    """Load strategy state from JSON file"""
    # Support legacy single file for backward compatibility
    if not symbol and os.path.exists("strategy_state.json"):
        try:
            with open("strategy_state.json", 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading legacy strategy state: {e}")
            return None
    
    if not symbol:
        return None
        
    filename = get_strategy_filename(symbol)
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading strategy state for {symbol}: {e}")
        return None

def load_all_strategies() -> Dict[str, dict]:
    """Load all active strategies"""
    ensure_strategy_dir()
    strategies = {}
    
    # Check legacy file
    if os.path.exists("strategy_state.json"):
        try:
            with open("strategy_state.json", 'r') as f:
                state = json.load(f)
                if "symbol" in state:
                    strategies[state["symbol"]] = state
        except Exception as e:
            logger.error(f"Error loading legacy strategy: {e}")
    
    # Load from strategies directory
    if os.path.exists(STRATEGY_STATE_DIR):
        for filename in os.listdir(STRATEGY_STATE_DIR):
            if filename.startswith("strategy_") and filename.endswith(".json"):
                try:
                    with open(os.path.join(STRATEGY_STATE_DIR, filename), 'r') as f:
                        state = json.load(f)
                        if "symbol" in state:
                            strategies[state["symbol"]] = state
                except Exception as e:
                    logger.error(f"Error loading {filename}: {e}")
    return strategies

def save_strategy_state(state, symbol: Optional[str] = None):
    """Save strategy state to JSON file"""
    ensure_strategy_dir()
    
    # Get symbol from state if not provided
    symbol = symbol or state.get("symbol")
    
    if not symbol:
        # Legacy fallback
        filename = "strategy_state.json"
    else:
        filename = get_strategy_filename(symbol)
    
    try:
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        logger.info(f"Strategy state saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving strategy state: {e}")
        raise

def remove_strategy_state(symbol: Optional[str] = None):
    """Remove strategy state file"""
    if not symbol:
        # Legacy support - remove old file
        if os.path.exists("strategy_state.json"):
            os.remove("strategy_state.json")
            logger.info("Legacy strategy state file removed")
        return
    
    filename = get_strategy_filename(symbol)
    try:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"Strategy state file removed: {filename}")
    except Exception as e:
        logger.error(f"Error removing strategy state file: {e}")

# Exchange endpoints
@router.get("/markets", response_model=dict)
async def get_markets():
    """Get all available trading pairs"""
    try:
        markets = await exchange_manager.fetch_markets()
        pairs = [market.symbol for market in markets if market.active]
        return {"pairs": pairs}
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        raise HTTPException(status_code=503, detail=f"Unable to fetch markets: {str(e)}")

@router.get("/price/{symbol}")
async def get_price(symbol: str):
    """Get current price for a symbol"""
    try:
        price = await exchange_manager.get_current_price(symbol)
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {symbol}")
        return {"symbol": symbol, "price": float(price)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        raise HTTPException(status_code=503, detail=f"Unable to fetch price: {str(e)}")

@router.get("/balances")
async def get_balances():
    """Get account balances"""
    try:
        balances = await exchange_manager.fetch_all_balances()
        return {"success": True, "balances": balances}
    except Exception as e:
        logger.error(f"Error fetching balances: {e}")
        raise HTTPException(status_code=503, detail=f"Unable to fetch balances: {str(e)}")

@router.get("/positions")
async def get_positions():
    """Get current positions"""
    try:
        positions = await exchange_manager.fetch_positions()
        return {"success": True, "positions": [
            {
                "symbol": pos.symbol,
                "side": pos.side,
                "size": float(pos.size),
                "entry_price": float(pos.entry_price),
                "mark_price": float(pos.mark_price),
                "pnl": float(pos.pnl),
                "notional": float(pos.notional)
            }
            for pos in positions
        ]}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=503, detail=f"Unable to fetch positions: {str(e)}")

@router.post("/order")
async def place_order(order: OrderRequest):
    """Place a trading order"""
    try:
        # Validate market availability
        if not exchange_manager.is_market_available(order.symbol):
            raise HTTPException(status_code=400, detail=f"Market {order.symbol} is not available")
        
        # Get current price for market orders
        price = order.price
        if order.type == "market":
            current_price = await exchange_manager.get_current_price(order.symbol)
            if current_price is None:
                raise HTTPException(status_code=503, detail=f"Unable to get current price for {order.symbol}")
            price = float(current_price)
        
        # Place the order
        result = await exchange_manager.place_order(
            symbol=order.symbol,
            order_type=order.type,
            side=order.side,
            amount=order.amount,
            price=Decimal(str(price)) if price else None
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=f"Order failed: {result.error_message}")
        
        return {
            "success": True,
            "order_id": result.order_id,
            "filled": str(result.average_price) if result.average_price else "None",
            "status": "None"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

# Strategy endpoints
@router.post("/strategy/start")
async def start_strategy(request: StrategyStartRequest):
    """Start a new 4-phase trading strategy"""
    try:
        # Check if strategy is already running for this symbol
        existing_state = load_strategy_state(request.symbol)
        if existing_state:
            raise HTTPException(status_code=400, detail=f"Strategy already running for {request.symbol}. Stop it first.")
        
        # Validate market
        if not exchange_manager.is_market_available(request.symbol):
            raise HTTPException(status_code=400, detail=f"Market {request.symbol} is not available")
        
        # Get current price
        current_price = await exchange_manager.get_current_price(request.symbol)
        if current_price is None:
            raise HTTPException(status_code=503, detail=f"Unable to get current price for {request.symbol}")
        
        # Initialize strategy state with v6.0.0 structure
        initial_state = {
            "symbol": request.symbol,
            "unit_size": request.unit_size,
            "entry_price": float(current_price),
            "current_unit": 0,
            "peak_unit": 0,
            "valley_unit": None,
            "phase": "ADVANCE",
            "current_long_position": request.position_size_usd,
            "current_short_position": 0,
            "current_cash_position": 0,
            "position_fragment": None,  # Will be calculated at peak (10% of position value)
            "hedge_fragment": None,  # Will be calculated at valley (25% of short value)
            "temp_cash_fragment": None,  # For unit -5 reversal
            "temp_hedge_value": None,  # For recovery unit 5
            "last_price": float(current_price),
            "initial_position_allocation": request.position_size_usd,
            "current_position_allocation": request.position_size_usd,
            "leverage": request.leverage,
            "created_at": datetime.now().isoformat()
        }
        
        # Place initial long position
        amount = request.position_size_usd / float(current_price)
        order_result = await exchange_manager.place_order(
            symbol=request.symbol,
            order_type="market",
            side="buy",
            amount=amount,
            price=current_price
        )
        
        if not order_result.success:
            raise HTTPException(status_code=400, detail=f"Failed to place initial order: {order_result.error_message}")
        
        # Save strategy state
        save_strategy_state(initial_state)
        
        logger.info(f"Started 4-phase strategy for {request.symbol} at ${current_price}")
        
        return {
            "success": True,
            "message": "Strategy started successfully",
            "initial_state": initial_state,
            "order_id": order_result.order_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.get("/strategies")
async def get_all_strategies():
    """Get all active strategies"""
    try:
        strategies = load_all_strategies()
        return {
            "success": True,
            "count": len(strategies),
            "strategies": strategies
        }
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.get("/strategy/{symbol}/status")
async def get_strategy_status_by_symbol(symbol: str):
    """Get strategy status for specific symbol"""
    try:
        # URL decode the symbol (FastAPI should do this automatically)
        state = load_strategy_state(symbol)
        if not state:
            raise HTTPException(status_code=404, detail=f"No active strategy found for {symbol}")
        
        return {
            "success": True,
            "strategy_active": True,
            "state": state
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.get("/strategy/status")
async def get_strategy_status():
    """Get current strategy status"""
    try:
        state = load_strategy_state()
        if not state:
            raise HTTPException(status_code=404, detail="No active strategy found")
        
        return {
            "success": True,
            "strategy_active": True,
            "state": state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/update-all")
async def update_all_strategies():
    """Update all active positions based on current prices"""
    try:
        strategies = load_all_strategies()
        if not strategies:
            raise HTTPException(status_code=404, detail="No active positions found")
        
        results = {}
        for symbol, state in strategies.items():
            try:
                result = await update_single_strategy(state)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                results[symbol] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "updated": len(results),
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategies: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

async def update_single_strategy(state: dict):
    """Update a single strategy state"""
    symbol = state["symbol"]
    
    # Get current price - use state price if it's been manually set for testing
    if "test_price" in state and state["test_price"] is not None:
        current_price = float(state["test_price"])
        logger.info(f"Using test price for {symbol}: ${current_price}")
    else:
        current_price = await exchange_manager.get_current_price(symbol)
        if current_price is None:
            raise Exception(f"Unable to get current price for {symbol}")
        current_price = float(current_price)
    
    entry_price = state["entry_price"]
    unit_size = state["unit_size"]
    
    # Calculate current unit based on price movement
    price_change = current_price - entry_price
    current_unit = int(price_change / unit_size)
    
    # Check if unit changed
    if current_unit == state["current_unit"]:
        # No unit change, just update price
        state["last_price"] = current_price
        save_strategy_state(state)
        return {"success": True, "message": "No unit change", "current_unit": current_unit}
    
    logger.info(f"{symbol} unit change: {state['current_unit']} -> {current_unit} (Phase: {state['phase']})")
    
    # Update current unit
    old_unit = state["current_unit"]
    state["current_unit"] = current_unit
    state["last_price"] = current_price
    
    trades_executed = []
    
    # Execute 4-phase logic based on current phase and unit change
    if state["phase"] == "ADVANCE":
        if current_unit > state["peak_unit"]:
            # New peak reached - calculate position_fragment
            state["peak_unit"] = current_unit
            
            # Get current position value from exchange
            positions = await exchange_manager.fetch_positions()
            position = next((p for p in positions if p.symbol == state["symbol"]), None)
            if position:
                position_value = abs(float(position.notional) if position.notional else float(position.size) * current_price)
                state["position_fragment"] = position_value * 0.10  # 10% of current position value
                logger.info(f"New peak reached: {current_unit}, position_fragment: ${state['position_fragment']:.2f}")
            else:
                # Fallback to using tracked position
                state["position_fragment"] = state["current_long_position"] * 0.10
                logger.info(f"New peak reached: {current_unit}, position_fragment (fallback): ${state['position_fragment']:.2f}")
                
        elif current_unit < state["peak_unit"]:
            # First decline from peak - transition to RETRACEMENT
            state["phase"] = "RETRACEMENT"
            logger.info("Phase transition: ADVANCE -> RETRACEMENT")
            # Continue to RETRACEMENT logic immediately
    
    if state["phase"] == "RETRACEMENT":
        units_from_peak = state["peak_unit"] - current_unit
        position_fragment = state.get("position_fragment", state["current_long_position"] * 0.10)
        
        # Determine what action to take based on units from peak
        # Using the exact logic from strategy_draft.md
        if units_from_peak == 1:
            # Sell 1 fragment long, short 1 fragment
            if state["current_long_position"] > 0:
                sell_amount = min(position_fragment, state["current_long_position"])
                sell_coins = sell_amount / current_price
                
                # Sell long position
                order_result = await exchange_manager.place_order(
                    symbol=state["symbol"],
                    order_type="market",
                    side="sell",
                    amount=sell_coins,
                    price=Decimal(str(current_price))
                )
                
                if order_result.success:
                    state["current_long_position"] -= sell_amount
                    state["current_short_position"] += position_fragment
                    state["current_cash_position"] += 0  # All proceeds go to short
                    trades_executed.append(f"Unit -1: Sold ${sell_amount:.2f} long, shorted ${position_fragment:.2f}")
                    logger.info(f"RETRACEMENT -1: Sold ${sell_amount:.2f}, shorted ${position_fragment:.2f}")
                    
        elif units_from_peak in [2, 3, 4]:
            # Sell 2 fragments long, short 1 fragment, 1 fragment to cash
            if state["current_long_position"] > 0:
                sell_amount = min(2 * position_fragment, state["current_long_position"])
                sell_coins = sell_amount / current_price
                
                # Sell long position
                order_result = await exchange_manager.place_order(
                    symbol=state["symbol"],
                    order_type="market",
                    side="sell",
                    amount=sell_coins,
                    price=Decimal(str(current_price))
                )
                
                if order_result.success:
                    state["current_long_position"] -= sell_amount
                    state["current_short_position"] += position_fragment
                    state["current_cash_position"] += position_fragment
                    trades_executed.append(f"Unit {units_from_peak}: Sold ${sell_amount:.2f}, shorted ${position_fragment:.2f}, cash ${position_fragment:.2f}")
                    logger.info(f"RETRACEMENT {units_from_peak}: Sold ${sell_amount:.2f}, short ${position_fragment:.2f}, cash ${position_fragment:.2f}")
                    
        elif units_from_peak == 5:
            # Sell remaining long, save as temp_cash_fragment, add to short
            if state["current_long_position"] > 0:
                remaining_long = state["current_long_position"]
                sell_coins = remaining_long / current_price
                
                # Sell all remaining long
                order_result = await exchange_manager.place_order(
                    symbol=state["symbol"],
                    order_type="market",
                    side="sell",
                    amount=sell_coins,
                    price=Decimal(str(current_price))
                )
                
                if order_result.success:
                    state["temp_cash_fragment"] = remaining_long
                    state["current_long_position"] = 0
                    state["current_short_position"] += remaining_long
                    trades_executed.append(f"Unit -5: Sold remaining ${remaining_long:.2f} long to short")
                    logger.info(f"RETRACEMENT -5: Sold remaining ${remaining_long:.2f} to short")
                    
        elif units_from_peak >= 6:
            # Transition to DECLINE phase
            state["phase"] = "DECLINE"
            state["valley_unit"] = current_unit
            logger.info("Phase transition: RETRACEMENT -> DECLINE")
            
        # Handle reversals (moving back toward peak)
        elif current_unit > old_unit and units_from_peak > 0:
            # Price moving back up - reverse the last action
            # TODO: Implement full reversal logic based on strategy_draft.md
            logger.info(f"RETRACEMENT reversal: units from peak {units_from_peak}")
            
            # Check if back to peak (back to ADVANCE)
            if units_from_peak == 0:
                state["phase"] = "ADVANCE"
                logger.info("Phase transition: RETRACEMENT -> ADVANCE")
    
    elif state["phase"] == "DECLINE":
        if state["valley_unit"] is None or current_unit < state["valley_unit"]:
            # New valley - update valley_unit
            state["valley_unit"] = current_unit
            logger.info(f"New valley reached: {current_unit}")
        
        units_from_valley = current_unit - state["valley_unit"] if state["valley_unit"] is not None else 0
        
        if units_from_valley == 1:
            # Calculate hedge_fragment (25% of short position value)
            if state["current_short_position"] > 0:
                state["hedge_fragment"] = state["current_short_position"] * 0.25
                logger.info(f"Valley +1: Calculated hedge_fragment: ${state['hedge_fragment']:.2f}")
        elif units_from_valley >= 2:
            # Transition to RECOVERY at +2 units from valley
            state["phase"] = "RECOVERY"
            logger.info("Phase transition: DECLINE -> RECOVERY")
    
    elif state["phase"] == "RECOVERY":
        units_from_valley = current_unit - state["valley_unit"]
        hedge_fragment = state.get("hedge_fragment", state["current_short_position"] * 0.25)
        position_fragment = state.get("position_fragment", state["initial_position_allocation"] * 0.10)
        
        if units_from_valley in [2, 3, 4]:
            # Close 1 hedge_fragment short, buy 1 hedge_fragment + 1 position_fragment long
            if state["current_short_position"] > 0:
                # Close short position
                close_short_amount = min(hedge_fragment, state["current_short_position"])
                close_coins = close_short_amount / current_price
                
                # Buy to close short and go long
                total_buy = hedge_fragment + position_fragment
                buy_coins = total_buy / current_price
                
                order_result = await exchange_manager.place_order(
                    symbol=state["symbol"],
                    order_type="market",
                    side="buy",
                    amount=buy_coins,
                    price=Decimal(str(current_price))
                )
                
                if order_result.success:
                    state["current_short_position"] -= close_short_amount
                    state["current_long_position"] += hedge_fragment
                    state["current_cash_position"] -= position_fragment
                    trades_executed.append(f"Unit +{units_from_valley}: Closed ${close_short_amount:.2f} short, bought ${total_buy:.2f} long")
                    logger.info(f"RECOVERY +{units_from_valley}: Closed ${close_short_amount:.2f} short, bought ${total_buy:.2f}")
                    
        elif units_from_valley == 5:
            # Close remaining short, buy all proceeds + 1 position_fragment
            if state["current_short_position"] > 0:
                remaining_short = state["current_short_position"]
                state["temp_hedge_value"] = remaining_short
                
                # Buy to close all short and go long
                total_buy = remaining_short + position_fragment
                buy_coins = total_buy / current_price
                
                order_result = await exchange_manager.place_order(
                    symbol=state["symbol"],
                    order_type="market",
                    side="buy",
                    amount=buy_coins,
                    price=Decimal(str(current_price))
                )
                
                if order_result.success:
                    state["current_short_position"] = 0
                    state["current_long_position"] += remaining_short
                    state["current_cash_position"] -= position_fragment
                    trades_executed.append(f"Unit +5: Closed remaining ${remaining_short:.2f} short, bought ${total_buy:.2f} long")
                    logger.info(f"RECOVERY +5: Closed remaining ${remaining_short:.2f} short, bought ${total_buy:.2f}")
                    
        elif units_from_valley >= 6:
            # RESET - should be fully long now
            if state["current_short_position"] == 0 and state["current_cash_position"] <= position_fragment:
                # Trigger RESET mechanism
                state["phase"] = "ADVANCE"
                state["current_unit"] = 0
                state["peak_unit"] = 0
                state["valley_unit"] = None
                state["position_fragment"] = None
                state["hedge_fragment"] = None
                state["temp_cash_fragment"] = None
                state["temp_hedge_value"] = None
                
                # Update current_position_allocation to new margin value
                positions = await exchange_manager.fetch_positions()
                position = next((p for p in positions if p.symbol == state["symbol"]), None)
                if position:
                    state["current_position_allocation"] = abs(float(position.notional) if position.notional else float(position.size) * current_price) / state["leverage"]
                
                # Reset entry price to current price
                state["entry_price"] = current_price
                
                logger.info(f"RESET triggered - back to ADVANCE phase. New allocation: ${state['current_position_allocation']:.2f}")
    
    save_strategy_state(state)
    return {
        "success": True,
        "symbol": symbol,
        "unit_change": f"{old_unit} -> {current_unit}",
        "phase": state["phase"],
        "trades_executed": trades_executed
    }

@router.post("/strategy/update/{symbol:path}")
async def update_strategy_by_symbol(symbol: str):
    """Update specific position based on current price"""
    try:
        # URL decode the symbol
        import urllib.parse
        symbol = urllib.parse.unquote(symbol)
        
        state = load_strategy_state(symbol)
        if not state:
            raise HTTPException(status_code=404, detail=f"No active position found for {symbol}")
        
        result = await update_single_strategy(state)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/update")
async def update_strategy():
    """Update strategy based on current price (legacy single-strategy support)"""
    try:
        # Try legacy file first
        state = load_strategy_state()
        if not state:
            # If no legacy file, update all strategies
            return await update_all_strategies()
        
        # Delegate to update_single_strategy
        result = await update_single_strategy(state)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
@router.post("/strategy/stop/{symbol}")
async def stop_strategy_by_symbol(symbol: str):
    """Stop strategy for specific symbol"""
    try:
        # URL decode the symbol
        import urllib.parse
        symbol = urllib.parse.unquote(symbol)
        
        state = load_strategy_state(symbol)
        if not state:
            raise HTTPException(status_code=404, detail=f"No active strategy found for {symbol}")
        
        # Remove strategy state file
        remove_strategy_state(symbol)
        
        logger.info(f"Stopped strategy for {symbol}")
        
        return {
            "success": True,
            "message": f"Strategy stopped successfully for {symbol}",
            "final_state": state
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/stop")
async def stop_strategy():
    """Stop the current strategy (legacy support)"""
    try:
        # Try legacy file first
        state = load_strategy_state()
        if not state:
            raise HTTPException(status_code=404, detail="No active strategy found")
        
        symbol = state.get("symbol")
        
        # Stop WebSocket monitoring if active
        from app.services.unit_tracker import unit_tracker
        if unit_tracker.running:
            await unit_tracker.stop_tracking()
        
        # Remove strategy state file
        if symbol:
            remove_strategy_state(symbol)
        else:
            remove_strategy_state()
        
        logger.info(f"Stopped strategy for {symbol or 'unknown'}")
        
        return {
            "success": True,
            "message": "Strategy stopped successfully",
            "final_state": state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/start-monitoring")
async def start_monitoring():
    """Start WebSocket-based real-time monitoring for the active strategy"""
    try:
        from app.services.unit_tracker import unit_tracker
        
        state = load_strategy_state()
        if not state:
            raise HTTPException(status_code=404, detail="No active strategy found")
        
        symbol = state.get("symbol")
        if not symbol:
            raise HTTPException(status_code=400, detail="No symbol in strategy state")
        
        # Define callback for unit changes
        async def on_unit_change(old_unit: int, new_unit: int, price: float):
            logger.info(f"WebSocket unit change: {old_unit} -> {new_unit} at ${price:.2f}")
            # Could trigger update_strategy here automatically
            # For now, just log the change
        
        # Start tracking in background
        import asyncio
        asyncio.create_task(unit_tracker.start_tracking(symbol, on_unit_change))
        
        logger.info(f"Started WebSocket monitoring for {symbol}")
        
        return {
            "success": True,
            "message": f"WebSocket monitoring started for {symbol}",
            "state": state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/stop-monitoring")
async def stop_monitoring():
    """Stop WebSocket-based monitoring"""
    try:
        from app.services.unit_tracker import unit_tracker
        
        if unit_tracker.running:
            await unit_tracker.stop_tracking()
            return {
                "success": True,
                "message": "WebSocket monitoring stopped"
            }
        else:
            return {
                "success": False,
                "message": "No active monitoring to stop"
            }
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")