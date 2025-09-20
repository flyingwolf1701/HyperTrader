import asyncio
import os
from decimal import Decimal
from typing import Dict
from loguru import logger
from dotenv import load_dotenv
from eth_account import Account

# Import the new SDK-based WebSocket client
from src.exchange.websocket_client import HyperliquidSDKClient
from src.exchange.hyperliquid_sdk import HyperliquidSDK
from src.strategy.position_map import PositionMap
from src.strategy.unit_tracker import UnitTracker

# Load environment variables
load_dotenv()

# --- Configuration ---
COIN = "SOL"
TESTNET = True
TARGET_UNITS = Decimal("5")
GRID_SPACING = Decimal("0.001") # e.g., 0.1% grid spacing

# --- Setup Logging ---
logger.add("sol_bot_log.txt", rotation="10 MB", level="DEBUG")

# --- Callback Handlers ---
async def handle_order_fill(position_map: PositionMap, order_id: str, filled_price: Decimal, filled_size: Decimal):
    """Callback function to handle order fill events from the WebSocket."""
    logger.success(f"Callback received: Order {order_id} filled. Price: {filled_price}, Size: {filled_size}")
    await position_map.handle_order_fill(order_id, filled_price, filled_size)

async def handle_new_order(order_data: dict):
    """Callback function to handle new order confirmations."""
    logger.info(f"New order confirmed by exchange: {order_data}")

async def handle_cancel_order(cancel_data: dict):
    """Callback function to handle order cancellation confirmations."""
    logger.warning(f"Order cancellation confirmed: {cancel_data}")

async def strategy_task(position_map: PositionMap, unit_tracker: UnitTracker):
    """The main trading strategy logic loop."""
    logger.info("Starting main strategy task...")
    
    # Wait for the first price update before starting
    await unit_tracker.wait_for_first_price_update()
    logger.info("First price update received. Initializing strategy.")
    
    while True:
        try:
            await asyncio.sleep(15) # Strategy execution interval
            logger.debug("Running strategy check...")
            
            current_price = unit_tracker.get_current_price()
            current_units = position_map.get_current_units()
            
            if current_price is not None:
                logger.info(f"Strategy Check | Price: ${current_price:.2f} | Current Units: {current_units}/{TARGET_UNITS}")
                # Example Logic:
                # if current_units < TARGET_UNITS:
                #     await position_map.place_entry_grid(current_price)
            else:
                logger.warning("Strategy Check | No price data available yet.")

        except asyncio.CancelledError:
            logger.warning("Strategy task cancelled.")
            break
        except Exception as e:
            logger.error(f"An error occurred in the strategy task: {e}")
            await asyncio.sleep(30) # Wait longer after an error

async def main():
    """Main function to initialize and run the trading bot."""
    logger.info("Initializing trading bot...")
    
    # --- Load Wallet ---
    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    if not private_key:
        logger.error("FATAL: HYPERLIQUID_PRIVATE_KEY environment variable not set.")
        return
        
    try:
        account = Account.from_key(private_key)
        user_address = account.address
        logger.success(f"Wallet loaded for address: {user_address}")
    except Exception as e:
        logger.error(f"Failed to load wallet from private key: {e}")
        return

    # --- Initialize Components ---
    # The REST API Client MUST be initialized first to get metadata
    exchange_sdk = HyperliquidSDK(wallet_address=user_address, is_mainnet=not TESTNET)
    await exchange_sdk.initialize()
    
    # Get asset config DYNAMICALLY from the SDK's cached metadata
    asset_meta = exchange_sdk.get_asset_meta(COIN)
    if not asset_meta:
        logger.error(f"Could not retrieve metadata for {COIN}. Exiting.")
        return

    # Create an asset_config dict on-the-fly. This keeps the PositionMap's
    # constructor clean and avoids changing its interface for now.
    asset_config = {
        "size_decimals": asset_meta.get("szDecimals", 2) # Default to 2 if not found
    }
    
    # Position and Order Management
    position_map = PositionMap(
        asset=COIN, 
        unit_tracker=UnitTracker(grid_spacing=GRID_SPACING, target_units=TARGET_UNITS),
        exchange=exchange_sdk,
        asset_config=asset_config
    )
    unit_tracker = position_map.unit_tracker
    
    # Initialize WebSocket Client using the SDK-based version
    ws_client = HyperliquidSDKClient(account=account, testnet=TESTNET)
    await ws_client.connect()

    # --- Setup Callbacks & Subscriptions ---
    fill_handler = lambda oid, price, size: handle_order_fill(position_map, oid, price, size)
    
    await ws_client.subscribe_to_trades(
        symbol=COIN, 
        price_callback=unit_tracker.update_price
    )
    
    await ws_client.subscribe_to_user_events(
        fill_callback=fill_handler,
        order_callback=handle_new_order,
        cancel_callback=handle_cancel_order
    )

    # --- Start All Tasks ---
    logger.info("Starting all background tasks...")
    ws_task = ws_client.start_listening()
    strategy = asyncio.create_task(strategy_task(position_map, unit_tracker))

    try:
        await asyncio.gather(ws_task, strategy)
    except KeyboardInterrupt:
        logger.warning("Shutdown signal received. Cleaning up...")
    finally:
        logger.info("Closing WebSocket connection...")
        await ws_client.disconnect()
        strategy.cancel()
        logger.info("Cancelling open orders...")
        await exchange_sdk.cancel_all_orders()
        logger.success("Bot shut down successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")

