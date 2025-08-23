import asyncio
from decimal import Decimal
from loguru import logger

from app.services.exchange import exchange_manager

class MarketDataManager:
    """
    A simplified class to manage market data.
    In the new architecture, the primary price fetching is handled directly
    within the WebSocket loop for each active trading plan.
    This class can be expanded later for other purposes if needed.
    """
    def __init__(self):
        self._is_running = False
        self._monitor_task = None
        logger.info("MarketDataManager initialized.")

    async def start_monitoring(self):
        """
        Starts a background monitoring task.
        Currently, this does not actively poll for prices as that is
        handled by the active WebSocket connections.
        """
        if self._is_running:
            logger.warning("Monitoring is already running.")
            return

        self._is_running = True
        # self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Market data monitoring started (currently idle).")

    async def stop_monitoring(self):
        """Stops the background monitoring task."""
        if not self._is_running or not self._monitor_task:
            return

        self._is_running = False
        self._monitor_task.cancel()
        try:
            await self._monitor_task
        except asyncio.CancelledError:
            logger.info("Market data monitoring task cancelled.")
        self._monitor_task = None
        logger.info("Market data monitoring stopped.")

    # The _monitor_loop is no longer needed as websockets handle their own price updates.
    # async def _monitor_loop(self):
    #     """Main loop for fetching market data."""
    #     while self._is_running:
    #         try:
    #             # This logic is now handled per-connection in websockets.py
    #             pass
    #         except Exception as e:
    #             logger.error(f"Error in market data loop: {e}", exc_info=True)
    #         await asyncio.sleep(10) # Interval for general checks if needed in future


# Create a single instance for the application to use.
market_data_manager = MarketDataManager()
