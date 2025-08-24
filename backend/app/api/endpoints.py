from fastapi import APIRouter, HTTPException
from typing import List, Optional
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

# Strategy state file path
STRATEGY_STATE_FILE = "strategy_state.json"

def load_strategy_state():
    """Load strategy state from JSON file"""
    if not os.path.exists(STRATEGY_STATE_FILE):
        return None
    try:
        with open(STRATEGY_STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading strategy state: {e}")
        return None

def save_strategy_state(state):
    """Save strategy state to JSON file"""
    try:
        with open(STRATEGY_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        logger.info("Strategy state saved to file")
    except Exception as e:
        logger.error(f"Error saving strategy state: {e}")
        raise

def remove_strategy_state():
    """Remove strategy state file"""
    try:
        if os.path.exists(STRATEGY_STATE_FILE):
            os.remove(STRATEGY_STATE_FILE)
            logger.info("Strategy state file removed")
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
        # Check if strategy is already running
        existing_state = load_strategy_state()
        if existing_state:
            raise HTTPException(status_code=400, detail="Strategy already running. Stop current strategy first.")
        
        # Validate market
        if not exchange_manager.is_market_available(request.symbol):
            raise HTTPException(status_code=400, detail=f"Market {request.symbol} is not available")
        
        # Get current price
        current_price = await exchange_manager.get_current_price(request.symbol)
        if current_price is None:
            raise HTTPException(status_code=503, detail=f"Unable to get current price for {request.symbol}")
        
        # Calculate decline portion (fixed trade size)
        decline_portion = request.position_size_usd / 12
        
        # Initialize strategy state  
        initial_state = {
            "symbol": request.symbol,
            "unit_size": request.unit_size,
            "entry_price": float(current_price),
            "current_unit": 0,
            "peak_unit": 0,
            "valley_unit": None,
            "phase": "ADVANCE",
            "current_long_position": request.position_size_usd,  # Net long position (can go negative for shorts)
            "decline_portion": decline_portion,  # Fixed trade size
            "last_price": float(current_price),
            "position_size_usd": request.position_size_usd,
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

@router.post("/strategy/update")
async def update_strategy():
    """Update strategy based on current price and execute trades"""
    try:
        state = load_strategy_state()
        if not state:
            raise HTTPException(status_code=404, detail="No active strategy found")
        
        # Get current price
        current_price = await exchange_manager.get_current_price(state["symbol"])
        if current_price is None:
            raise HTTPException(status_code=503, detail=f"Unable to get current price for {state['symbol']}")
        
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
            return {"success": True, "message": "No unit change detected", "state": state}
        
        logger.info(f"Unit change detected: {state['current_unit']} -> {current_unit} (Phase: {state['phase']})")
        
        # Update current unit
        old_unit = state["current_unit"]
        state["current_unit"] = current_unit
        state["last_price"] = current_price
        
        # Execute 4-phase logic based on current phase and unit change
        trades_executed = []
        
        if state["phase"] == "ADVANCE":
            if current_unit > state["peak_unit"]:
                # New peak reached
                state["peak_unit"] = current_unit
                logger.info(f"New peak reached: {current_unit}")
            elif current_unit < state["peak_unit"]:
                # First decline from peak - transition to RETRACEMENT
                state["phase"] = "RETRACEMENT"
                logger.info("Phase transition: ADVANCE -> RETRACEMENT")
        
        elif state["phase"] == "RETRACEMENT":
            if current_unit < old_unit:
                # Price declining further - execute sell/short pattern based on distance from peak
                units_from_peak = state["peak_unit"] - current_unit
                decline_portion = state["decline_portion"]
                
                # Determine sell and short amounts based on unit distance
                if units_from_peak == 1:
                    # -1 unit: sell 1x, short 1x
                    net_change = -2 * decline_portion  # net position decreases by 2x decline_portion
                elif units_from_peak == 2:
                    # -2 units: sell 2x more, short 1x more (total change from -1 to -2)
                    net_change = -3 * decline_portion  # additional -3x from previous -2x = -5x total
                elif units_from_peak == 3:
                    # -3 units: sell 2x more, short 1x more (total change from -2 to -3)  
                    net_change = -3 * decline_portion  # additional -3x from previous -5x = -8x total
                elif units_from_peak == 4:
                    # -4 units: sell 2x more, short 1x more (fully short)
                    net_change = -3 * decline_portion  # additional -3x from previous -8x = -11x total
                elif units_from_peak >= 5:
                    # -5+ units: emergency sell remaining long
                    net_change = -state["current_long_position"]  # sell everything remaining
                else:
                    net_change = 0
                    
                if net_change != 0:
                    # Calculate actual trade amount
                    trade_amount_usd = abs(net_change)
                    trade_coins = trade_amount_usd / current_price
                    
                    # Execute the trade (sell if reducing long, buy if increasing short)
                    if net_change < 0:  # Reducing long position (selling/shorting)
                        order_result = await exchange_manager.place_order(
                            symbol=state["symbol"],
                            order_type="market",
                            side="sell", 
                            amount=trade_coins,
                            price=Decimal(str(current_price))
                        )
                        
                        if order_result.success:
                            state["current_long_position"] += net_change  # Decrease position
                            trades_executed.append(f"RETRACEMENT: Net position change ${net_change:.2f} at unit {current_unit}")
                            logger.info(f"RETRACEMENT: Net position change ${net_change:.2f} at unit {current_unit}")
                            
                            # Check if fully short (position went negative)
                            if state["current_long_position"] <= -state["position_size_usd"] * 0.8:  # Nearly fully short
                                state["phase"] = "DECLINE" 
                                state["valley_unit"] = current_unit
                                logger.info("Phase transition: RETRACEMENT -> DECLINE")
            
            elif current_unit > old_unit:
                # Price oscillating back up during retracement - reverse the trades
                units_from_peak = state["peak_unit"] - current_unit
                decline_portion = state["decline_portion"]
                
                # Calculate how much to buy back based on current distance from peak
                if units_from_peak >= 0:  # Still below peak
                    # Determine the net position we should be at for this unit level
                    target_position_change = 0
                    if units_from_peak == 0:
                        target_position_change = 0  # Back at peak, should be fully long
                    elif units_from_peak == 1:
                        target_position_change = -2 * decline_portion
                    elif units_from_peak == 2:
                        target_position_change = -5 * decline_portion  
                    elif units_from_peak == 3:
                        target_position_change = -8 * decline_portion
                    elif units_from_peak >= 4:
                        target_position_change = -11 * decline_portion
                    
                    expected_position = state["position_size_usd"] + target_position_change
                    position_adjustment = expected_position - state["current_long_position"]
                    
                    if position_adjustment > 0:  # Need to buy back
                        trade_amount_usd = position_adjustment
                        trade_coins = trade_amount_usd / current_price
                        
                        order_result = await exchange_manager.place_order(
                            symbol=state["symbol"],
                            order_type="market",
                            side="buy",
                            amount=trade_coins,
                            price=Decimal(str(current_price))
                        )
                        
                        if order_result.success:
                            state["current_long_position"] = expected_position
                            trades_executed.append(f"RETRACEMENT REVERSAL: Bought back ${trade_amount_usd:.2f} at unit {current_unit}")
                            logger.info(f"RETRACEMENT REVERSAL: Bought back ${trade_amount_usd:.2f} at unit {current_unit}")
                            
                            # Check if back to fully long (back to ADVANCE)
                            if state["current_long_position"] >= state["position_size_usd"] * 0.9:
                                state["phase"] = "ADVANCE"
                                logger.info("Phase transition: RETRACEMENT -> ADVANCE")
        
        elif state["phase"] == "DECLINE":
            if state["valley_unit"] is None or current_unit < state["valley_unit"]:
                # New valley
                state["valley_unit"] = current_unit
                logger.info(f"New valley reached: {current_unit}")
            elif current_unit > state["valley_unit"]:
                # First uptick from valley - transition to RECOVERY
                state["phase"] = "RECOVERY"
                logger.info("Phase transition: DECLINE -> RECOVERY")
        
        elif state["phase"] == "RECOVERY":
            if current_unit > old_unit:
                # Price rising - cover shorts and re-enter long using position_value / 4 pattern
                units_from_valley = current_unit - state["valley_unit"]
                
                # When fully short, take current portfolio value and divide by 4 for re-entry
                if units_from_valley <= 4 and state["current_long_position"] < 0:
                    # Calculate current portfolio value (position_size + unrealized PnL from short position)
                    current_portfolio_value = state["position_size_usd"] + (
                        abs(state["current_long_position"]) * (state["entry_price"] - current_price) / state["entry_price"]
                    )
                    recovery_portion = current_portfolio_value / 4
                    
                    # Execute buy to cover short and go long
                    buy_coins = recovery_portion / current_price
                    order_result = await exchange_manager.place_order(
                        symbol=state["symbol"],
                        order_type="market",
                        side="buy",
                        amount=buy_coins,
                        price=Decimal(str(current_price))
                    )
                    
                    if order_result.success:
                        state["current_long_position"] += recovery_portion
                        trades_executed.append(f"RECOVERY: Bought ${recovery_portion:.2f} at unit {current_unit}")
                        logger.info(f"RECOVERY: Bought ${recovery_portion:.2f} at unit {current_unit}")
                        
                        # Check if back to full long position
                        if state["current_long_position"] >= state["position_size_usd"] * 0.9:  # Nearly fully long
                            state["phase"] = "ADVANCE"
                            state["peak_unit"] = current_unit  
                            state["valley_unit"] = None
                            # Reset entry price for new cycle
                            state["entry_price"] = current_price
                            logger.info("System reset - back to ADVANCE phase")
        
        # Save updated state
        save_strategy_state(state)
        
        return {
            "success": True,
            "unit_change": f"{old_unit} -> {current_unit}",
            "phase": state["phase"],
            "trades_executed": trades_executed,
            "state": state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router.post("/strategy/stop")
async def stop_strategy():
    """Stop the current strategy"""
    try:
        state = load_strategy_state()
        if not state:
            raise HTTPException(status_code=404, detail="No active strategy found")
        
        # Remove strategy state file
        remove_strategy_state()
        
        logger.info(f"Stopped strategy for {state.get('symbol', 'unknown')}")
        
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