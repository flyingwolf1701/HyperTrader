from fastapi import APIRouter, HTTPException
from app.services.exchange import exchange_manager
from decimal import Decimal
import logging
import json
import os
from typing import Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Strategy state file
STRATEGY_STATE_FILE = "strategy_state.json"

class StrategyState(BaseModel):
    symbol: str
    unit_size: float
    entry_price: float
    current_unit: int
    peak_unit: int
    valley_unit: Optional[int]
    phase: str  # ADVANCE, RETRACEMENT, DECLINE, RECOVERY
    long_invested: float
    long_cash: float
    hedge_short: float
    last_price: float
    position_size_usd: float

class StrategyConfig(BaseModel):
    symbol: str
    position_size_usd: float
    unit_size: float
    leverage: int = 1

# Strategy management functions
def load_strategy_state() -> Optional[StrategyState]:
    """Load strategy state from file"""
    try:
        if os.path.exists(STRATEGY_STATE_FILE):
            with open(STRATEGY_STATE_FILE, 'r') as f:
                data = json.load(f)
                return StrategyState(**data)
    except Exception as e:
        logger.error(f"Error loading strategy state: {e}")
    return None

def save_strategy_state(state: StrategyState):
    """Save strategy state to file"""
    try:
        with open(STRATEGY_STATE_FILE, 'w') as f:
            json.dump(state.dict(), f, indent=2)
        logger.info(f"Strategy state saved: {state.phase} phase, unit {state.current_unit}")
    except Exception as e:
        logger.error(f"Error saving strategy state: {e}")

def calculate_current_unit(current_price: float, entry_price: float, unit_size: float) -> int:
    """Calculate current unit based on price movement from entry"""
    price_diff = current_price - entry_price
    return int(price_diff / unit_size)

def get_scaling_amount(state: StrategyState, phase: str) -> float:
    """Get the amount to trade based on phase and scaling rules"""
    total_value = state.long_invested + state.long_cash + abs(state.hedge_short)
    
    if phase == "RETRACEMENT":
        # Sell 12% of total position value
        return total_value * 0.12
    elif phase == "RECOVERY":
        # Buy back 25% of available cash/shorts
        available = state.long_cash + abs(state.hedge_short)
        return available * 0.25
    
    return 0.0

@router.get("/positions")
async def get_positions():
    """Get all current positions from the exchange."""
    try:
        positions = await exchange_manager.fetch_positions()
        
        logger.info(f"Raw positions from exchange: {len(positions)} positions")
        
        position_data = []
        all_positions = []  # Debug: show all positions, even zero-size
        
        for pos in positions:
            pos_info = {
                "symbol": pos.symbol,
                "side": pos.side,
                "size": float(pos.size),
                "notional": float(pos.notional),
                "entry_price": float(pos.entry_price) if pos.entry_price else None,
                "mark_price": float(pos.mark_price) if pos.mark_price else None,
                "pnl": float(pos.pnl) if pos.pnl else None,
                "pnl_percentage": float(pos.pnl_percentage) if pos.pnl_percentage else None
            }
            all_positions.append(pos_info)
            
            if abs(pos.size) > 0:  # Only show positions with actual size
                position_data.append(pos_info)
                logger.info(f"Found active position: {pos.symbol} {pos.side} {pos.size}")
        
        return {
            "success": True,
            "positions": position_data,
            "all_positions_debug": all_positions[:10],  # Show first 10 for debugging
            "total_fetched": len(positions),
            "count": len(position_data)
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{symbol:path}")
async def get_price(symbol: str):
    """Get current price for a symbol."""
    try:
        # Handle URL encoding for symbols with slashes
        import urllib.parse
        symbol = urllib.parse.unquote(symbol)
        
        logger.info(f"Fetching price for symbol: {symbol}")
        
        # Check if the symbol exists in our markets
        if not exchange_manager.is_market_available(symbol):
            available_symbols = list(exchange_manager.markets.keys())[:10]  # Show first 10 for debugging
            logger.warning(f"Symbol {symbol} not found. Available symbols include: {available_symbols}")
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not available. Check /markets for available symbols.")
        
        price = await exchange_manager.get_current_price(symbol)
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {symbol}")
        
        return {
            "symbol": symbol,
            "price": float(price)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order")
async def place_order(order_data: dict):
    """Place a simple order."""
    try:
        symbol = order_data["symbol"]
        side = order_data["side"]
        amount = order_data["amount"]
        order_type = order_data.get("type", "market")
        params = order_data.get("params", {})
        
        logger.info(f"Attempting order: {side} {amount} {symbol}")
        
        # Format amount to exchange precision (like reference code)
        formatted_amount = exchange_manager.exchange.amount_to_precision(symbol, amount)
        formatted_amount = float(formatted_amount)
        
        # Handle price based on order type
        price_arg = None
        if order_type == "limit":
            price_arg = float(order_data.get("price", 0))
            price_arg = exchange_manager.exchange.price_to_precision(symbol, price_arg)
            price_arg = float(price_arg)
        elif order_type == "market":
            # HyperLiquid requires price for market orders (for slippage calculation)
            if "price" in order_data:
                price_arg = float(order_data["price"])
            else:
                # Get current price and add 5% slippage for buy, subtract for sell
                current_price = await exchange_manager.get_current_price(symbol)
                if current_price:
                    slippage_multiplier = 1.05 if side == "buy" else 0.95
                    price_arg = float(current_price) * slippage_multiplier
                    logger.info(f"Auto-calculated market price with slippage: {price_arg}")
            if price_arg:
                price_arg = exchange_manager.exchange.price_to_precision(symbol, price_arg)
                price_arg = float(price_arg)
        
        logger.info(f"Formatted amount: {formatted_amount}, price: {price_arg}")
        
        # Call ccxt directly following reference pattern
        raw_order = await exchange_manager.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=formatted_amount,
            price=price_arg,
            params=params
        )
        
        logger.info(f"Order successful: {raw_order}")
        
        return {
            "success": True,
            "order_id": str(raw_order.get("id", "unknown")) if raw_order else "no_response",
            "filled": str(raw_order.get("filled", 0)) if raw_order else "0",
            "status": str(raw_order.get("status", "unknown")) if raw_order else "unknown"
        }
    except Exception as e:
        logger.error(f"Error placing order: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)[:200]
        }


@router.get("/balances")
async def get_balances():
    """Get account balances."""
    try:
        balances = await exchange_manager.fetch_all_balances()
        return {
            "success": True,
            "balances": balances
        }
    except Exception as e:
        logger.error(f"Error getting balances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/markets")
async def get_markets():
    """Get available trading pairs."""
    try:
        markets = await exchange_manager.fetch_markets()
        pairs = [market.symbol for market in markets[:50]]  # Limit for testing
        return {"pairs": pairs}
    except Exception as e:
        logger.error(f"Error getting markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Strategy endpoints
@router.post("/strategy/start")
async def start_strategy(config: StrategyConfig):
    """Start the 4-phase hedging strategy"""
    try:
        # Get current price
        current_price = await exchange_manager.get_current_price(config.symbol)
        if not current_price:
            raise HTTPException(status_code=400, detail=f"Could not get price for {config.symbol}")
        
        price_float = float(current_price)
        
        # Initialize strategy state
        state = StrategyState(
            symbol=config.symbol,
            unit_size=config.unit_size,
            entry_price=price_float,
            current_unit=0,
            peak_unit=0,
            valley_unit=None,
            phase="ADVANCE",
            long_invested=config.position_size_usd,
            long_cash=0.0,
            hedge_short=0.0,
            last_price=price_float,
            position_size_usd=config.position_size_usd
        )
        
        # Place initial long order
        amount = config.position_size_usd / price_float
        formatted_amount = exchange_manager.exchange.amount_to_precision(config.symbol, amount)
        
        order_response = await exchange_manager.exchange.create_order(
            symbol=config.symbol,
            type="market",
            side="buy",
            amount=float(formatted_amount),
            price=None,
            params={}
        )
        
        # Save state
        save_strategy_state(state)
        
        return {
            "success": True,
            "message": "Strategy started",
            "state": state.dict(),
            "initial_order_id": order_response.get("id"),
            "entry_price": price_float
        }
        
    except Exception as e:
        logger.error(f"Error starting strategy: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@router.post("/strategy/update")  
async def update_strategy():
    """Update strategy based on current price - main strategy logic"""
    try:
        # Load current state
        state = load_strategy_state()
        if not state:
            return {"success": False, "error": "No active strategy found"}
        
        # Get current price
        current_price = await exchange_manager.get_current_price(state.symbol)
        if not current_price:
            return {"success": False, "error": f"Could not get price for {state.symbol}"}
        
        price_float = float(current_price)
        previous_unit = state.current_unit
        new_unit = calculate_current_unit(price_float, state.entry_price, state.unit_size)
        
        # Check if we need to take action (only on whole unit changes)
        if new_unit == previous_unit:
            state.last_price = price_float
            save_strategy_state(state)
            return {"success": True, "message": "No action needed", "current_unit": new_unit, "phase": state.phase}
        
        logger.info(f"Unit change detected: {previous_unit} -> {new_unit} (Phase: {state.phase})")
        
        orders_placed = []
        state.current_unit = new_unit
        state.last_price = price_float
        
        # 4-Phase Strategy Logic
        if state.phase == "ADVANCE":
            # Track peaks
            if new_unit > state.peak_unit:
                state.peak_unit = new_unit
                logger.info(f"New peak reached: {state.peak_unit}")
            
            # Check for decline (first drop from peak)
            elif new_unit < state.peak_unit:
                # Transition to RETRACEMENT
                state.phase = "RETRACEMENT"
                
                # Sell first 12% chunk
                sell_amount_usd = get_scaling_amount(state, "RETRACEMENT")
                sell_amount_tokens = sell_amount_usd / price_float
                
                if sell_amount_tokens > 0:
                    formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, sell_amount_tokens)
                    
                    order = await exchange_manager.exchange.create_order(
                        symbol=state.symbol,
                        type="market", 
                        side="sell",
                        amount=float(formatted_amount),
                        price=None,
                        params={}
                    )
                    
                    # Update state
                    state.long_invested -= sell_amount_usd
                    state.long_cash += sell_amount_usd
                    
                    orders_placed.append({"type": "sell", "amount": sell_amount_usd, "order_id": order.get("id")})
                    logger.info(f"RETRACEMENT: Sold ${sell_amount_usd:.2f} at unit {new_unit}")
        
        elif state.phase == "RETRACEMENT":
            # Continue scaling down on further declines
            if new_unit < previous_unit:
                sell_amount_usd = get_scaling_amount(state, "RETRACEMENT")
                
                # Check if we have long positions left to sell
                if state.long_invested > sell_amount_usd:
                    sell_amount_tokens = sell_amount_usd / price_float
                    formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, sell_amount_tokens)
                    
                    order = await exchange_manager.exchange.create_order(
                        symbol=state.symbol,
                        type="market",
                        side="sell", 
                        amount=float(formatted_amount),
                        price=None,
                        params={}
                    )
                    
                    state.long_invested -= sell_amount_usd
                    state.long_cash += sell_amount_usd
                    orders_placed.append({"type": "sell", "amount": sell_amount_usd, "order_id": order.get("id")})
                    
                # Check if long position is exhausted -> DECLINE phase
                if state.long_invested <= 10:  # Small threshold for rounding
                    state.phase = "DECLINE"
                    state.valley_unit = new_unit
                    logger.info(f"Transitioned to DECLINE phase at unit {new_unit}")
            
            # Recovery during retracement
            elif new_unit > previous_unit:
                state.phase = "RECOVERY"
                # Buy back 25% of available funds
                buy_amount_usd = get_scaling_amount(state, "RECOVERY")
                
                if buy_amount_usd > 0 and state.long_cash > buy_amount_usd:
                    buy_amount_tokens = buy_amount_usd / price_float
                    formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, buy_amount_tokens)
                    
                    order = await exchange_manager.exchange.create_order(
                        symbol=state.symbol,
                        type="market",
                        side="buy",
                        amount=float(formatted_amount), 
                        price=None,
                        params={}
                    )
                    
                    state.long_cash -= buy_amount_usd
                    state.long_invested += buy_amount_usd
                    orders_placed.append({"type": "buy", "amount": buy_amount_usd, "order_id": order.get("id")})
        
        elif state.phase == "DECLINE":
            # Track valleys
            if new_unit < (state.valley_unit or 0):
                state.valley_unit = new_unit
                logger.info(f"New valley reached: {state.valley_unit}")
            
            # Check for recovery
            elif new_unit > (state.valley_unit or 0):
                state.phase = "RECOVERY"
                
                # Buy back first 25% chunk
                buy_amount_usd = get_scaling_amount(state, "RECOVERY") 
                
                if buy_amount_usd > 0 and state.long_cash > buy_amount_usd:
                    buy_amount_tokens = buy_amount_usd / price_float
                    formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, buy_amount_tokens)
                    
                    order = await exchange_manager.exchange.create_order(
                        symbol=state.symbol,
                        type="market",
                        side="buy", 
                        amount=float(formatted_amount),
                        price=None,
                        params={}
                    )
                    
                    state.long_cash -= buy_amount_usd
                    state.long_invested += buy_amount_usd
                    orders_placed.append({"type": "buy", "amount": buy_amount_usd, "order_id": order.get("id")})
        
        elif state.phase == "RECOVERY":
            # Continue buying back on further recovery
            if new_unit > previous_unit:
                buy_amount_usd = get_scaling_amount(state, "RECOVERY")
                
                if buy_amount_usd > 0 and state.long_cash > buy_amount_usd:
                    buy_amount_tokens = buy_amount_usd / price_float
                    formatted_amount = exchange_manager.exchange.amount_to_precision(state.symbol, buy_amount_tokens)
                    
                    order = await exchange_manager.exchange.create_order(
                        symbol=state.symbol,
                        type="market",
                        side="buy",
                        amount=float(formatted_amount),
                        price=None, 
                        params={}
                    )
                    
                    state.long_cash -= buy_amount_usd
                    state.long_invested += buy_amount_usd
                    orders_placed.append({"type": "buy", "amount": buy_amount_usd, "order_id": order.get("id")})
                
                # Check for system reset (all funds back in long)
                if state.long_cash <= 10 and state.hedge_short == 0:
                    # Reset to ADVANCE phase
                    state.phase = "ADVANCE"
                    state.entry_price = price_float
                    state.current_unit = 0
                    state.peak_unit = 0
                    state.valley_unit = None
                    logger.info(f"System reset - back to ADVANCE phase at price ${price_float}")
        
        # Save updated state
        save_strategy_state(state)
        
        return {
            "success": True,
            "unit_change": f"{previous_unit} -> {new_unit}",
            "phase": state.phase,
            "orders_placed": orders_placed,
            "state": {
                "long_invested": state.long_invested,
                "long_cash": state.long_cash,
                "hedge_short": state.hedge_short,
                "current_unit": state.current_unit,
                "peak_unit": state.peak_unit,
                "valley_unit": state.valley_unit
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating strategy: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@router.get("/strategy/status")
async def get_strategy_status():
    """Get current strategy status"""
    try:
        state = load_strategy_state()
        if not state:
            return {"success": False, "error": "No active strategy found"}
        
        # Get current price for unit calculation
        current_price = await exchange_manager.get_current_price(state.symbol)
        if current_price:
            current_unit = calculate_current_unit(float(current_price), state.entry_price, state.unit_size)
        else:
            current_unit = state.current_unit
            
        return {
            "success": True,
            "strategy_active": True,
            "symbol": state.symbol,
            "phase": state.phase,
            "current_price": float(current_price) if current_price else state.last_price,
            "entry_price": state.entry_price,
            "unit_size": state.unit_size,
            "current_unit": current_unit,
            "peak_unit": state.peak_unit,
            "valley_unit": state.valley_unit,
            "positions": {
                "long_invested": state.long_invested,
                "long_cash": state.long_cash,
                "hedge_short": state.hedge_short,
                "total_value": state.long_invested + state.long_cash + abs(state.hedge_short)
            }
        }
    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return {"success": False, "error": str(e)}

@router.post("/strategy/stop")
async def stop_strategy():
    """Stop the strategy and clean up"""
    try:
        if os.path.exists(STRATEGY_STATE_FILE):
            os.remove(STRATEGY_STATE_FILE)
            logger.info("Strategy stopped and state file removed")
            return {"success": True, "message": "Strategy stopped"}
        else:
            return {"success": False, "error": "No active strategy found"}
    except Exception as e:
        logger.error(f"Error stopping strategy: {e}")
        return {"success": False, "error": str(e)}