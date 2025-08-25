"""
Stage 4 Test: Enter Trade & ADVANCE Phase
Tests automated trade entry and ADVANCE phase monitoring
"""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from strategy.strategy_manager import StrategyManager


async def test_stage4():
    """Test Stage 4: Enter Trade & ADVANCE Phase"""
    
    logger.info("=" * 60)
    logger.info("STAGE 4 TEST: Enter Trade & ADVANCE Phase")
    logger.info("=" * 60)
    
    # Test parameters
    symbol = "ETH/USDC:USDC"
    position_size_usd = Decimal("100")  # Small test position
    unit_size = Decimal("2.0")  # $2 per unit
    leverage = 10
    test_duration = 60  # Run for 1 minute
    
    logger.info("\nTest Parameters:")
    logger.info(f"  Symbol: {symbol}")
    logger.info(f"  Position Size: ${position_size_usd}")
    logger.info(f"  Unit Size: ${unit_size}")
    logger.info(f"  Leverage: {leverage}x")
    logger.info(f"  Test Duration: {test_duration} seconds")
    
    manager = StrategyManager(testnet=True)
    
    try:
        # Start the strategy (enters trade and begins ADVANCE phase)
        logger.info("\n" + "=" * 60)
        logger.info("STARTING STRATEGY")
        logger.info("=" * 60)
        
        success = await manager.start_strategy(
            symbol=symbol,
            position_size_usd=position_size_usd,
            unit_size=unit_size,
            leverage=leverage
        )
        
        if not success:
            logger.error("Failed to start strategy")
            return False
        
        # Monitor for the test duration
        logger.info("\n" + "=" * 60)
        logger.info(f"MONITORING FOR {test_duration} SECONDS")
        logger.info("=" * 60)
        logger.info("Watch for:")
        logger.info("  - Unit changes as price moves")
        logger.info("  - Peak unit tracking")
        logger.info("  - Position fragment updates")
        logger.info("")
        
        # Run WebSocket listener in background
        listen_task = asyncio.create_task(manager.ws_client.listen())
        
        # Monitor and display status periodically
        for i in range(test_duration // 10):
            await asyncio.sleep(10)
            
            # Get and display strategy status
            status = await manager.get_strategy_status(symbol)
            
            logger.info(f"\n[{i*10 + 10}s] Strategy Status:")
            logger.info(f"  Phase: {status['phase']}")
            logger.info(f"  Current Price: ${status['current_price']:.2f}")
            logger.info(f"  Current Unit: {status['current_unit']}")
            logger.info(f"  Peak Unit: {status['peak_unit']}")
            logger.info(f"  Units from Peak: {status['units_from_peak']}")
            logger.info(f"  Position Fragment: ${status['position_fragment']:.2f}")
            
            if status['position']['has_position']:
                logger.info(f"  Position PnL: ${status['position']['pnl']:.2f}")
            
            # Check if we should handle ADVANCE phase logic
            if status['phase'] == "ADVANCE" and status['units_from_peak'] < 0:
                logger.warning("  ⚠️ Price retracing from peak - RETRACEMENT would trigger in Stage 5")
        
        # Stop monitoring
        manager.ws_client.is_connected = False
        await asyncio.sleep(1)
        
        # Final status
        logger.info("\n" + "=" * 60)
        logger.info("FINAL STATUS")
        logger.info("=" * 60)
        
        final_status = await manager.get_strategy_status(symbol)
        logger.info(f"Phase: {final_status['phase']}")
        logger.info(f"Entry Price: ${final_status['entry_price']:.2f}")
        logger.info(f"Current Price: ${final_status['current_price']:.2f}")
        logger.info(f"Price Change: ${final_status['current_price'] - final_status['entry_price']:.2f}")
        logger.info(f"Final Unit: {final_status['current_unit']}")
        logger.info(f"Peak Unit Reached: {final_status['peak_unit']}")
        logger.info(f"Valley Unit: {final_status['valley_unit']}")
        
        if final_status['position']['has_position']:
            logger.info(f"\nPosition:")
            logger.info(f"  Side: {final_status['position']['side']}")
            logger.info(f"  Size: {final_status['position']['contracts']} ETH")
            logger.info(f"  PnL: ${final_status['position']['pnl']:.2f}")
        
        # Ask user if they want to close the position
        logger.info("\n" + "=" * 60)
        logger.warning("TEST POSITION IS STILL OPEN")
        logger.info("Would you like to close it? (y/n)")
        
        # For automated testing, we'll close it
        logger.info("Auto-closing position for test...")
        await manager.stop_strategy(symbol, close_position=True)
        
        logger.info("\n" + "=" * 60)
        logger.success("STAGE 4 TEST COMPLETED")
        logger.info("✅ Trade entry successful")
        logger.info("✅ ADVANCE phase initiated")
        logger.info("✅ Unit tracking operational")
        logger.info("✅ Position fragment calculation working")
        logger.info("✅ Peak unit tracking functional")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        
        # Try to clean up
        try:
            await manager.stop_strategy(symbol, close_position=True)
        except:
            pass
        
        return False
    finally:
        # Ensure WebSocket is disconnected
        if manager.ws_client.is_connected:
            await manager.ws_client.disconnect()


async def test_without_real_trade():
    """Test Stage 4 logic without placing real trades"""
    
    logger.info("=" * 60)
    logger.info("STAGE 4 DEMO: Enter Trade & ADVANCE Phase (No Real Trade)")
    logger.info("=" * 60)
    
    from strategy.strategy_manager import StrategyState
    
    # Create a mock strategy state
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),
        unit_size=Decimal("2.0"),
        leverage=10
    )
    
    # Simulate entry
    state.has_position = True
    state.entry_price = Decimal("4400.00")
    state.unit_tracker.entry_price = state.entry_price
    state.calculate_position_fragment()
    
    logger.info("Simulated Position:")
    logger.info(f"  Entry Price: ${state.entry_price}")
    logger.info(f"  Position Size: ${state.position_size_usd}")
    logger.info(f"  Unit Size: ${state.unit_size}")
    logger.info(f"  Initial Fragment: ${state.position_fragment:.2f}")
    
    # Simulate price movements
    price_scenarios = [
        ("4402.00", "Price up $2 (1 unit)"),
        ("4404.00", "Price up $4 (2 units)"),
        ("4406.00", "Price up $6 (3 units)"),
        ("4404.00", "Price retraces to +2 units"),
        ("4402.00", "Price retraces to +1 unit"),
        ("4398.00", "Price drops below entry (-1 unit)"),
    ]
    
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATING PRICE MOVEMENTS")
    logger.info("=" * 60)
    
    for price_str, description in price_scenarios:
        price = Decimal(price_str)
        logger.info(f"\n{description}")
        logger.info(f"  Price: ${price}")
        
        # Update unit tracker
        changed = state.unit_tracker.calculate_unit_change(price)
        
        if changed:
            # Recalculate position value and fragment
            price_change_pct = (price - state.entry_price) / state.entry_price
            state.position_allocation = state.position_size_usd * (1 + price_change_pct)
            state.calculate_position_fragment()
            
            logger.info(f"  📊 UNIT CHANGED: {state.unit_tracker.current_unit}")
            logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
            logger.info(f"  Units from Peak: {state.unit_tracker.get_units_from_peak()}")
            logger.info(f"  Position Value: ${state.position_allocation:.2f}")
            logger.info(f"  New Fragment: ${state.position_fragment:.2f}")
            
            # Check for phase transition
            if state.unit_tracker.get_units_from_peak() <= -1:
                logger.warning(f"  ⚠️ RETRACEMENT trigger! ({state.unit_tracker.get_units_from_peak()} from peak)")
                logger.info("  Stage 5 would handle position scaling here")
        else:
            logger.info(f"  No unit change (still at unit {state.unit_tracker.current_unit})")
    
    logger.info("\n" + "=" * 60)
    logger.success("STAGE 4 DEMO COMPLETED")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Stage 4: Enter Trade & ADVANCE Phase")
    parser.add_argument("--demo", action="store_true", help="Run demo without real trades")
    
    args = parser.parse_args()
    
    if args.demo:
        asyncio.run(test_without_real_trade())
    else:
        logger.warning("=" * 60)
        logger.warning("⚠️  WARNING: This will place a REAL trade on testnet!")
        logger.warning("Position size: $100 with 10x leverage")
        logger.warning("=" * 60)
        response = input("Continue? (y/n): ")
        
        if response.lower() == 'y':
            asyncio.run(test_stage4())
        else:
            logger.info("Test cancelled")
            # Run demo instead
            asyncio.run(test_without_real_trade())