"""
Unit tracking service for the v6.0.0 strategy
Processes price feeds and translates them into unit changes
Based on Stage 2 of the development plan
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from decimal import Decimal
from datetime import datetime

from app.services.websocket import websocket_manager
from app.api.endpoints import load_strategy_state, save_strategy_state
from app.services.exchange import exchange_manager

logger = logging.getLogger(__name__)


class UnitTracker:
    """Tracks unit changes and triggers strategy updates"""
    
    def __init__(self):
        """Initialize the unit tracker"""
        self.current_state: Optional[Dict[str, Any]] = None
        self.last_unit: Optional[int] = None
        self.unit_change_callback: Optional[Callable] = None
        self.running = False
        
    def calculate_unit_change(self, current_price: float) -> Optional[int]:
        """
        Calculate if a unit change has occurred
        Based on Stage 2 of development plan
        
        Args:
            current_price: The current market price
            
        Returns:
            New unit value if changed, None otherwise
        """
        if not self.current_state:
            return None
            
        entry_price = self.current_state.get("entry_price")
        unit_size = self.current_state.get("unit_size")
        
        if not entry_price or not unit_size:
            logger.error("Missing entry_price or unit_size in state")
            return None
        
        # Calculate price delta from entry
        price_delta = current_price - entry_price
        
        # Calculate current unit (whole units only)
        current_unit = int(price_delta / unit_size)
        
        # Check if unit has changed
        if self.last_unit is None or current_unit != self.last_unit:
            logger.info(f"Unit change detected: {self.last_unit} -> {current_unit}")
            self.last_unit = current_unit
            return current_unit
            
        return None
    
    async def on_price_update(self, price: float, timestamp: str):
        """
        Handle price updates from WebSocket
        
        Args:
            price: Current market price
            timestamp: Timestamp of the update
        """
        try:
            # Calculate if unit changed
            new_unit = self.calculate_unit_change(price)
            
            if new_unit is not None:
                # Update state
                old_unit = self.current_state.get("current_unit", 0)
                self.current_state["current_unit"] = new_unit
                self.current_state["last_price"] = price
                
                # Log unit change
                logger.info(f"[{timestamp}] Unit change: {old_unit} -> {new_unit} (Price: ${price:.2f})")
                
                # Trigger callback if registered
                if self.unit_change_callback:
                    await self.trigger_unit_change_callback(old_unit, new_unit, price)
                    
                # Save updated state
                save_strategy_state(self.current_state)
                
        except Exception as e:
            logger.error(f"Error processing price update: {e}")
    
    async def trigger_unit_change_callback(self, old_unit: int, new_unit: int, price: float):
        """
        Trigger the unit change callback
        
        Args:
            old_unit: Previous unit value
            new_unit: New unit value
            price: Current price
        """
        if self.unit_change_callback:
            try:
                if asyncio.iscoroutinefunction(self.unit_change_callback):
                    await self.unit_change_callback(old_unit, new_unit, price)
                else:
                    self.unit_change_callback(old_unit, new_unit, price)
            except Exception as e:
                logger.error(f"Error in unit change callback: {e}")
    
    async def start_tracking(self, symbol: str, unit_change_callback: Optional[Callable] = None):
        """
        Start tracking unit changes for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., "ETH/USDC:USDC")
            unit_change_callback: Optional callback for unit changes
        """
        try:
            # Load current strategy state
            self.current_state = load_strategy_state()
            
            if not self.current_state:
                logger.error("No active strategy found")
                return False
            
            if self.current_state.get("symbol") != symbol:
                logger.error(f"Symbol mismatch: expected {symbol}, got {self.current_state.get('symbol')}")
                return False
            
            # Set initial unit
            self.last_unit = self.current_state.get("current_unit", 0)
            
            # Register callback
            self.unit_change_callback = unit_change_callback
            
            # Extract coin from symbol (e.g., "ETH/USDC:USDC" -> "ETH")
            coin = symbol.split("/")[0]
            
            # Connect to WebSocket if not already connected
            if not websocket_manager.websocket:
                await websocket_manager.connect()
            
            # Subscribe to trades with our price handler
            await websocket_manager.subscribe_to_trades(coin, self.on_price_update)
            
            self.running = True
            logger.info(f"Started unit tracking for {symbol}")
            
            # Start listening
            await websocket_manager.listen()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting unit tracker: {e}")
            return False
    
    async def stop_tracking(self):
        """Stop tracking unit changes"""
        self.running = False
        await websocket_manager.disconnect()
        logger.info("Stopped unit tracking")
    
    def get_current_unit(self) -> Optional[int]:
        """Get the current unit value"""
        return self.last_unit
    
    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get the current strategy state"""
        return self.current_state


# Global unit tracker instance
unit_tracker = UnitTracker()


async def test_unit_tracking():
    """Test the unit tracking functionality"""
    
    # Test data setup
    test_state = {
        "symbol": "ETH/USDC:USDC",
        "unit_size": 2.0,  # $2 per unit
        "entry_price": 3450.00,
        "current_unit": 0,
        "peak_unit": 0,
        "valley_unit": None,
        "phase": "ADVANCE"
    }
    
    # Save test state
    save_strategy_state(test_state)
    
    # Unit change callback
    async def on_unit_change(old_unit: int, new_unit: int, price: float):
        print(f"Unit changed: {old_unit} -> {new_unit} at price ${price:.2f}")
        
        # Determine phase action based on state
        state = unit_tracker.get_state()
        phase = state.get("phase")
        
        if phase == "ADVANCE":
            if new_unit > state.get("peak_unit", 0):
                print(f"  New peak reached: {new_unit}")
            elif new_unit < state.get("peak_unit", 0):
                print(f"  Entering RETRACEMENT phase")
        elif phase == "RETRACEMENT":
            units_from_peak = state.get("peak_unit", 0) - new_unit
            print(f"  RETRACEMENT: {units_from_peak} units from peak")
    
    # Create tracker
    tracker = UnitTracker()
    
    # Test price updates
    print("\nTest Case 1: Upward unit change")
    print("Setup: entry_price = $3450.00, unit_size = $2.00, current_unit = 0")
    
    # Simulate price of $3452.50 (should trigger unit change to 1)
    await tracker.on_price_update(3452.50, datetime.now().isoformat())
    
    print("\nTest Case 2: Downward unit change")
    # Simulate price of $3447.50 (should trigger unit change to -1)
    await tracker.on_price_update(3447.50, datetime.now().isoformat())
    
    print("\nTest Case 3: No unit change")
    # Simulate price of $3451.50 (should not trigger unit change)
    await tracker.on_price_update(3451.50, datetime.now().isoformat())
    
    print("\nTest completed")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_unit_tracking())