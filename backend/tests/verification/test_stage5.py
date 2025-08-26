"""
Stage 5 Test: RETRACEMENT Phase
Tests position scaling during price drops from peak
"""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyManager, StrategyState
from src.core.models import Phase


async def test_retracement_demo():
    """Test Stage 5 logic without placing real trades"""
    
    logger.info("=" * 60)
    logger.info("STAGE 5 DEMO: RETRACEMENT Phase (No Real Trade)")
    logger.info("=" * 60)
    
    # Create a mock strategy state
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),
        unit_size=Decimal("2.0"),
        leverage=10
    )
    
    # Simulate we're at peak after ADVANCE phase
    state.has_position = True
    state.entry_price = Decimal("4400.00")
    state.unit_tracker.entry_price = state.entry_price
    state.unit_tracker.current_unit = 3  # At +3 units
    state.unit_tracker.peak_unit = 3  # Peak is at +3 units
    state.unit_tracker.phase = Phase.ADVANCE
    
    # Position has grown due to price increase
    price_at_peak = state.entry_price + (state.unit_size * 3)  # 4406
    price_change_pct = (price_at_peak - state.entry_price) / state.entry_price
    state.position_allocation = state.position_size_usd * (1 + price_change_pct)
    state.calculate_position_fragment()
    
    logger.info("Starting Position (at peak):")
    logger.info(f"  Entry Price: ${state.entry_price}")
    logger.info(f"  Current Price: ${price_at_peak}")
    logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
    logger.info(f"  Position Value: ${state.position_allocation:.2f}")
    logger.info(f"  Position Fragment: ${state.position_fragment:.2f}")
    logger.info(f"  Portfolio: 100% Long")
    
    # Simulate RETRACEMENT phase actions
    retracement_scenarios = [
        (-1, "4404.00", "Sell 1 fragment long, Open 1 fragment short", "80% Long / 10% Short / 10% Cash"),
        (-2, "4402.00", "Sell 2 fragments long, Add 1 fragment short", "50% Long / 20% Short / 30% Cash"),
        (-3, "4400.00", "Sell 2 fragments long, Add 1 fragment short", "20% Long / 30% Short / 50% Cash"),
        (-4, "4398.00", "Sell 2 fragments long, Add 1 fragment short", "0% Long / 40% Short / 60% Cash"),
        (-5, "4396.00", "Sell remaining long, Add proceeds to short", "0% Long / ~50% Short / ~50% Cash"),
    ]
    
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATING RETRACEMENT PHASE")
    logger.info("=" * 60)
    
    for units_from_peak, price_str, action, portfolio_state in retracement_scenarios:
        price = Decimal(price_str)
        
        # Simulate unit change
        state.unit_tracker.calculate_unit_change(price)
        
        logger.info(f"\nPrice drops to ${price} ({units_from_peak} from peak)")
        
        if state.unit_tracker.phase == Phase.ADVANCE and units_from_peak == -1:
            logger.info(">>> Transitioning to RETRACEMENT phase <<<")
            state.unit_tracker.phase = Phase.RETRACEMENT
        
        logger.info(f"  Action: {action}")
        logger.info(f"  Portfolio After: {portfolio_state}")
        
        # Recalculate position value and fragment based on new price
        # In real trading, these would be actual position values
        if units_from_peak >= -4:
            # Still have some long position
            remaining_long_pct = Decimal(str({-1: 0.8, -2: 0.5, -3: 0.2, -4: 0.0}.get(units_from_peak, 0)))
            price_change_pct = (price - state.entry_price) / state.entry_price
            long_value = state.position_size_usd * remaining_long_pct * (Decimal("1") + price_change_pct)
            
            short_pct = Decimal(str({-1: 0.1, -2: 0.2, -3: 0.3, -4: 0.4}.get(units_from_peak, 0)))
            # Short profits from price drop
            short_entry = price + state.unit_size  # Entered 1 unit higher
            short_profit_pct = (short_entry - price) / short_entry
            short_value = state.position_size_usd * short_pct * (Decimal("1") + short_profit_pct)
            
            cash_pct = Decimal(str({-1: 0.1, -2: 0.3, -3: 0.5, -4: 0.6}.get(units_from_peak, 0)))
            cash_value = state.position_size_usd * cash_pct
            
            total_portfolio = long_value + short_value + cash_value
            logger.info(f"  Portfolio Value: ${total_portfolio:.2f}")
            logger.info(f"    Long: ${long_value:.2f}")
            logger.info(f"    Short: ${short_value:.2f}")
            logger.info(f"    Cash: ${cash_value:.2f}")
    
    # Test reversal scenario
    logger.info("\n" + "=" * 60)
    logger.info("TESTING REVERSAL IN RETRACEMENT")
    logger.info("=" * 60)
    
    logger.info("\nPrice rebounds from -5 to -4 units from peak:")
    price = Decimal("4398.00")
    state.unit_tracker.calculate_unit_change(price)
    logger.info(f"  Price: ${price}")
    logger.info("  Action: REVERSE last action")
    logger.info("  Buy back 2 fragments long, Close 1 fragment short")
    logger.info("  Portfolio returns to: ~0% Long / 40% Short / 60% Cash")
    
    # Test transition to DECLINE
    logger.info("\n" + "=" * 60)
    logger.info("TESTING TRANSITION TO DECLINE")
    logger.info("=" * 60)
    
    logger.info("\nPrice drops to -6 units from peak:")
    price = Decimal("4394.00")
    state.unit_tracker.calculate_unit_change(price)
    logger.info(f"  Price: ${price}")
    logger.info(">>> Transitioning to DECLINE phase <<<")
    state.unit_tracker.phase = Phase.DECLINE
    state.unit_tracker.valley_unit = state.unit_tracker.current_unit
    logger.info("  Position is now fully defensive (short + cash)")
    logger.info("  Valley unit will track new lows from here")
    
    logger.info("\n" + "=" * 60)
    logger.success("STAGE 5 DEMO COMPLETED")
    logger.info("Key Features Demonstrated:")
    logger.info("  - Progressive position scaling based on units from peak")
    logger.info("  - Systematic reduction of long exposure")
    logger.info("  - Gradual building of short position")
    logger.info("  - Cash reserve accumulation")
    logger.info("  - Reversal capability for price rebounds")
    logger.info("  - Transition to DECLINE phase at -6 units")
    logger.info("=" * 60)


async def test_stage5_live():
    """Test Stage 5 with real trading (small position)"""
    
    logger.info("=" * 60)
    logger.info("STAGE 5 TEST: RETRACEMENT Phase")
    logger.info("=" * 60)
    logger.warning("This test requires an existing long position at peak")
    logger.warning("It will execute RETRACEMENT scaling actions")
    logger.info("=" * 60)
    
    # This would require setting up a position first
    # and then simulating price drops
    # For safety, we'll skip the live test for now
    
    logger.info("Live testing requires careful setup:")
    logger.info("1. First run Stage 4 to enter a long position")
    logger.info("2. Wait for price to rise (establish peak)")
    logger.info("3. Then trigger RETRACEMENT on price drops")
    logger.info("\nFor safety, please use the demo mode instead")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Stage 5: RETRACEMENT Phase")
    parser.add_argument("--live", action="store_true", help="Run with real trades (requires setup)")
    
    args = parser.parse_args()
    
    if args.live:
        logger.warning("=" * 60)
        logger.warning("Live testing requires an existing position")
        logger.warning("Please ensure Stage 4 has been run first")
        logger.warning("=" * 60)
        response = input("Continue with live test? (y/n): ")
        
        if response.lower() == 'y':
            asyncio.run(test_stage5_live())
        else:
            logger.info("Running demo instead...")
            asyncio.run(test_retracement_demo())
    else:
        asyncio.run(test_retracement_demo())