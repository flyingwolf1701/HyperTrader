import asyncio
import logging
from typing import Dict
from fastapi import WebSocket
# from sqlalchemy.ext.asyncio import AsyncSession  # COMMENTED OUT FOR TESTING
# from sqlalchemy import select, update  # COMMENTED OUT FOR TESTING
from decimal import Decimal
import json

# from app.db.session import AsyncSessionLocal  # COMMENTED OUT FOR TESTING
from app.models.state import SystemState
# from app.schemas import TradingPlan  # COMMENTED OUT FOR TESTING
from app.services.exchange import exchange_manager
from app.services.trading_logic import run_trading_logic_for_state

# Import in-memory storage from endpoints
from app.api.endpoints_minimal import in_memory_trading_plans

logger = logging.getLogger(__name__)

class TradeManager:
    """
    Manages the lifecycle of all active trading plans.
    """
    def __init__(self):
        self.active_trades: Dict[str, asyncio.Task] = {}

    async def start_trade_monitoring(self, symbol: str):
        """Starts the monitoring task for a given symbol if not already running."""
        if symbol in self.active_trades and not self.active_trades[symbol].done():
            logger.warning(f"Monitoring for {symbol} is already active.")
            return

        logger.info(f"Starting trade monitoring for {symbol}.")
        # Create a background task for the trading loop
        task = asyncio.create_task(self._trade_loop(symbol))
        self.active_trades[symbol] = task

    async def stop_trade_monitoring(self, symbol: str):
        """Stops the monitoring task for a given symbol."""
        if symbol not in self.active_trades:
            logger.warning(f"No active monitoring task to stop for {symbol}.")
            return

        logger.info(f"Stopping trade monitoring for {symbol}.")
        task = self.active_trades.pop(symbol)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Monitoring for {symbol} cancelled successfully.")

    async def _trade_loop(self, symbol: str):
        """The main logic loop for an individual trading plan."""
        try:
            # 1. Fetch the initial trading plan state from in-memory storage
            trading_plan_data = in_memory_trading_plans.get(symbol)
            
            if not trading_plan_data:
                logger.error(f"Could not find active trading plan for {symbol} to start loop.")
                return

            # Parse the system state from JSON
            system_state_data = json.loads(trading_plan_data["system_state"])
            system_state = SystemState(**system_state_data)
            logger.info(f"Initial state for {symbol} loaded. Starting trading loop.")

            # 2. Start the continuous monitoring loop
            first_run = True
            while True:
                current_price = await exchange_manager.get_current_price(symbol)
                if current_price is None:
                    logger.warning(f"Could not retrieve price for {symbol}, skipping cycle.")
                    await asyncio.sleep(5)
                    continue

                # 3. Run the trading logic
                system_state = await run_trading_logic_for_state(system_state, current_price, sync_first_run=first_run)
                first_run = False  # Only sync on first run

                # 4. Save updated state to in-memory storage and file
                trading_plan_data["system_state"] = system_state.model_dump_json_safe()
                trading_plan_data["current_phase"] = system_state.current_phase
                in_memory_trading_plans[symbol] = trading_plan_data
                
                # Save to file to persist across restarts
                from app.api.endpoints_minimal import save_trading_plans
                save_trading_plans(in_memory_trading_plans)
                
                logger.info(f"Updated state for {symbol} in memory. Current phase: {system_state.current_phase}")

                await asyncio.sleep(10) # Main loop interval

        except asyncio.CancelledError:
            logger.info(f"Trade loop for {symbol} is shutting down.")
        except Exception as e:
            logger.error(f"Critical error in trade loop for {symbol}: {e}", exc_info=True)
        finally:
            logger.info(f"Trade loop for {symbol} has terminated.")

# Singleton instance of the manager
trade_manager = TradeManager()
