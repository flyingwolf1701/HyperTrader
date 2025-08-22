import asyncio
import logging
from typing import Dict
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from decimal import Decimal

from app.db.session import AsyncSessionLocal
from app.models.state import SystemState
from app.schemas import TradingPlan
from app.services.exchange import exchange_manager
from app.services.trading_logic import run_trading_logic_for_state

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
        async with AsyncSessionLocal() as db:
            try:
                # 1. Fetch the initial trading plan state
                result = await db.execute(
                    select(TradingPlan).where(
                        TradingPlan.symbol == symbol,
                        TradingPlan.is_active == "active"
                    ).order_by(TradingPlan.created_at.desc())
                )
                trading_plan = result.scalar_one_or_none()

                if not trading_plan:
                    logger.error(f"Could not find active trading plan for {symbol} to start loop.")
                    return

                system_state = SystemState(**trading_plan.system_state)
                logger.info(f"Initial state for {symbol} loaded. Starting trading loop.")

                # 2. Start the continuous monitoring loop
                while True:
                    current_price = await exchange_manager.get_current_price(symbol)
                    if current_price is None:
                        logger.warning(f"Could not retrieve price for {symbol}, skipping cycle.")
                        await asyncio.sleep(5)
                        continue

                    # 3. Run the trading logic
                    system_state = await run_trading_logic_for_state(system_state, current_price)

                    # 4. Persist the updated state to the database
                    await db.execute(
                        update(TradingPlan)
                        .where(TradingPlan.id == trading_plan.id)
                        .values(
                            system_state=system_state.dict(),
                            current_phase=system_state.current_phase
                        )
                    )
                    await db.commit()
                    logger.info(f"Updated state for {symbol} in DB. Current phase: {system_state.current_phase}")

                    await asyncio.sleep(10) # Main loop interval

            except asyncio.CancelledError:
                logger.info(f"Trade loop for {symbol} is shutting down.")
            except Exception as e:
                logger.error(f"Critical error in trade loop for {symbol}: {e}", exc_info=True)
            finally:
                logger.info(f"Trade loop for {symbol} has terminated.")

# Singleton instance of the manager
trade_manager = TradeManager()
