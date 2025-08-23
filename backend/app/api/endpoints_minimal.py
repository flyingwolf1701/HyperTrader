from fastapi import APIRouter, HTTPException, status
from typing import Dict
import logging
from decimal import Decimal
import json
import os
from datetime import datetime

from app.models.state import SystemState, TradingPlanCreate
from app.services.exchange import exchange_manager

# File-based persistence for trading plans
TRADING_PLANS_FILE = "trading_plans.json"

def load_trading_plans() -> Dict[str, dict]:
    """Load trading plans from file."""
    if os.path.exists(TRADING_PLANS_FILE):
        try:
            with open(TRADING_PLANS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error loading trading plans: {e}")
            return {}
    return {}

def save_trading_plans(plans: Dict[str, dict]):
    """Save trading plans to file."""
    try:
        with open(TRADING_PLANS_FILE, 'w') as f:
            json.dump(plans, f, indent=2)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error saving trading plans: {e}")

# Load existing trading plans on startup
in_memory_trading_plans: Dict[str, dict] = load_trading_plans()

logger = logging.getLogger(__name__)
router = APIRouter()


# Trading Plan Endpoints
@router.post("/trade/start", response_model=dict)
async def start_trading_plan(plan_data: TradingPlanCreate):
    """Start a new trading plan based on a desired position size in USD."""
    try:
        # 1. Get current price and calculate position
        symbol_to_use = plan_data.symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"

        current_price = await exchange_manager.get_current_price(symbol_to_use)
        if not current_price:
            raise HTTPException(status_code=400, detail=f"Could not get price for {symbol_to_use}")

        logger.info(f"Starting trading plan for {symbol_to_use} at price ${current_price}")

        # 2. Calculate position size based on leverage and desired USD amount
        entry_price = current_price
        leverage = plan_data.leverage
        total_position_value = plan_data.position_size_usd * leverage
        required_margin = plan_data.position_size_usd
        
        # 3. Place initial order (simulation for testing)
        position_size_coins = total_position_value / current_price
        
        # Mock order result for testing
        class MockOrderResult:
            def __init__(self):
                self.success = True
                self.order_id = f"mock_order_{datetime.now().strftime('%H%M%S')}"
                self.cost = float(total_position_value)
        
        order_result = MockOrderResult()
        actual_cost = Decimal(str(order_result.cost))
        
        # Calculate USD value per unit based on user-defined unit_size
        unit_value = (plan_data.unit_size * plan_data.position_size_usd) / (current_price * 100)
        
        system_state = SystemState(
            symbol=symbol_to_use,
            entry_price=entry_price,
            unit_size=plan_data.unit_size,
            unit_value=unit_value,
            required_margin=required_margin,
            leverage=plan_data.leverage,
            # ADVANCE phase: Single long position, no allocation split yet
            long_invested=actual_cost,  # All the initial position
            long_cash=Decimal("0"),
            hedge_long=Decimal("0"),  # No hedge position until retracement
            hedge_short=Decimal("0")
        )
        
        # Store in memory instead of database
        plan_id = f"{symbol_to_use}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        trading_plan_data = {
            "id": plan_id,
            "symbol": symbol_to_use,
            "system_state": system_state.model_dump_json_safe(),
            "initial_margin": float(required_margin),
            "leverage": plan_data.leverage,
            "unit_size": float(plan_data.unit_size),
            "current_phase": system_state.current_phase,
            "created_at": datetime.now().isoformat(),
            "is_active": "active"
        }
        
        # Store in memory and save to file
        in_memory_trading_plans[symbol_to_use] = trading_plan_data
        save_trading_plans(in_memory_trading_plans)
        
        logger.info(f"Started new trading plan for {symbol_to_use} with ID {plan_id}")
        
        # Start trade monitoring for this symbol
        from app.services.trade_manager import trade_manager
        await trade_manager.start_trade_monitoring(symbol_to_use)
        
        system_state_dict = system_state.dict()
        for key, value in system_state_dict.items():
            if isinstance(value, Decimal):
                system_state_dict[key] = float(value)

        return {
            "success": True,
            "plan_id": plan_id,
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
async def get_trading_state(symbol: str):
    """Get current trading state for a symbol"""
    try:
        symbol_to_use = symbol
        if "/" in symbol_to_use and ":" not in symbol_to_use:
            parts = symbol_to_use.split("/")
            if len(parts) == 2 and parts[1] == "USDC":
                symbol_to_use = f"{parts[0]}/USDC:USDC"

        # Use in-memory storage instead of database
        trading_plan_data = in_memory_trading_plans.get(symbol_to_use)
        
        if not trading_plan_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active trading plan found for {symbol_to_use}"
            )
        
        # Parse system state from JSON
        system_state_data = json.loads(trading_plan_data["system_state"])
        system_state = SystemState(**system_state_data)
        
        current_price = await exchange_manager.get_current_price(symbol_to_use)
        
        if current_price:
            system_state.current_price = current_price
        
        # Calculate current unit based on price change
        if system_state.unit_size > 0:
            total_price_change = system_state.current_price - system_state.entry_price
            current_unit = int(total_price_change / system_state.unit_size)
            system_state.current_unit = current_unit
        
        system_state_dict = system_state.dict()
        for key, value in system_state_dict.items():
            if isinstance(value, Decimal):
                system_state_dict[key] = float(value)
        
        return {
            "success": True,
            "symbol": symbol_to_use,
            "current_price": float(current_price) if current_price else None,
            "system_state": system_state_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trading state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}"
        )


@router.get("/trade/plans")
async def list_trading_plans():
    """List all active trading plans."""
    try:
        plans = []
        for symbol, plan_data in in_memory_trading_plans.items():
            system_state_data = json.loads(plan_data["system_state"])
            plans.append({
                "symbol": symbol,
                "plan_id": plan_data["id"],
                "current_phase": plan_data["current_phase"],
                "entry_price": system_state_data.get("entry_price"),
                "current_price": system_state_data.get("current_price"),
                "current_unit": system_state_data.get("current_unit"),
                "created_at": plan_data["created_at"]
            })
        
        return {
            "success": True,
            "plans": plans
        }
        
    except Exception as e:
        logger.error(f"Error listing trading plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Exchange Endpoints (simplified)
@router.get("/exchange/pairs")
async def get_trading_pairs():
    """Get available trading pairs."""
    try:
        markets = await exchange_manager.get_markets()
        pairs = [market.symbol for market in markets[:20]]  # Limit for testing
        return {"pairs": pairs}
    except Exception as e:
        logger.error(f"Error getting trading pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exchange/price/{symbol}")
async def get_price(symbol: str):
    """Get current price for a symbol."""
    try:
        price = await exchange_manager.get_current_price(symbol)
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {symbol}")
        
        return {
            "symbol": symbol,
            "price": float(price),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        raise HTTPException(status_code=500, detail=str(e))