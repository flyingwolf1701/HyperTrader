#!/usr/bin/env python3
"""
Test script to verify the new logging system works correctly.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

from app.core.logging import configure_logging, get_trade_logger, get_websocket_logger
from loguru import logger

def test_logging_system():
    """Test all aspects of the logging system."""
    
    print("Configuring logging system...")
    configure_logging()
    
    print("Testing general logging...")
    logger.info("Application started successfully")
    logger.debug("Debug information")
    logger.warning("Warning message")
    logger.error("Error message for testing")
    
    print("Testing trade-specific logging...")
    trade_logger = get_trade_logger("BTC/USDC")
    trade_logger.info("TRADE: Initial position opened - $1000 long")
    trade_logger.info("TRADE: Unit changed from 0 to 1. Price: $45000")
    trade_logger.info("TRADE: Phase transition from advance to retracement")
    trade_logger.info("TRADE: Placing sell order - Amount: $250.00 (0.005556 coins), Reduce-only: True, Phase: retracement")
    trade_logger.error("TRADE: Failed to place buy order for $100.00: Insufficient margin")
    
    print("Testing WebSocket logging...")
    ws_logger = get_websocket_logger("ETH/USDC")
    ws_logger.debug("WS: Connection established to price feed")
    ws_logger.info("WS: Price update received: $3200.50")
    ws_logger.warning("WS: Connection lost, attempting reconnection...")
    
    print("Logging test completed successfully!")
    print("Check the logs directory for generated files:")
    logs_dir = Path("logs")
    for log_file in logs_dir.glob("*.log"):
        print(f"   - {log_file.name}")

if __name__ == "__main__":
    test_logging_system()