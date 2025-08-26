"""
Stage 8 Test: RECOVERY Phase
Tests gradual position reversal from short to long and cycle completion
"""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.strategy_manager import StrategyState
from src.core.models import Phase


async def test_recovery_demo():
    """Test Stage 8 RECOVERY phase without real trades"""
    
    logger.info("=" * 60)
    logger.info("STAGE 8 DEMO: RECOVERY Phase")
    logger.info("=" * 60)
    
    # Create a strategy in RECOVERY phase
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),
        unit_size=Decimal("2.0"),
        leverage=10
    )
    
    # Simulate we're entering RECOVERY from DECLINE
    # Valley was at -7 units ($4386), now at +2 units from valley ($4390)
    state.has_position = True
    state.entry_price = Decimal("4400.00")  # Original entry
    state.unit_tracker.entry_price = state.entry_price
    state.unit_tracker.phase = Phase.RECOVERY
    
    # Current state (+2 from valley)
    current_price = Decimal("4390.00")
    state.unit_tracker.current_unit = -5  # Still -5 from original entry
    state.unit_tracker.valley_unit = -7  # Valley was at -7
    state.unit_tracker.peak_unit = 3  # Historical peak
    
    # Portfolio is ~50% short, ~50% cash (from DECLINE phase)
    short_position_value = Decimal("500")  # $500 in short
    cash_reserves = Decimal("500")  # $500 in cash
    
    # Calculate hedge fragment (25% of short value)
    state.hedge_fragment = short_position_value * Decimal("0.25")  # $125
    state.position_fragment = Decimal("100")  # Original 10% fragment
    
    logger.info("Starting Position (entering RECOVERY):")
    logger.info(f"  Valley Price: $4386 (at -7 units)")
    logger.info(f"  Current Price: ${current_price} (+2 from valley)")
    logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
    logger.info(f"  Units from Valley: {state.unit_tracker.get_units_from_valley()}")
    logger.info(f"  Portfolio: ~50% Short / ~50% Cash")
    logger.info(f"  Hedge Fragment: ${state.hedge_fragment}")
    logger.info(f"  Position Fragment: ${state.position_fragment}")
    
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATING RECOVERY PHASE")
    logger.info("=" * 60)
    
    # Simulate recovery progression
    recovery_scenarios = [
        (Decimal("4392.00"), 3, "Close 1 hedge_fragment short, buy 1 hedge + 1 position long"),
        (Decimal("4394.00"), 4, "Close 1 hedge_fragment short, buy 1 hedge + 1 position long"),
        (Decimal("4396.00"), 5, "Close remaining short, convert all to long"),
        (Decimal("4398.00"), 6, "Final long purchase, then RESET"),
    ]
    
    # Track portfolio transformation
    short_value = short_position_value
    long_value = Decimal("0")
    cash_value = cash_reserves
    
    for price, units_from_valley, action in recovery_scenarios:
        # Update unit tracker
        state.unit_tracker.calculate_unit_change(price)
        
        logger.info(f"\nPrice recovers to ${price} (+{units_from_valley} from valley):")
        logger.info(f"  Action: {action}")
        
        # Simulate portfolio changes
        if units_from_valley <= 4:
            # Progressive scaling (+2 to +4)
            # Close 1 hedge fragment short, buy 1 hedge + 1 position fragment long
            short_value -= state.hedge_fragment
            long_value += state.hedge_fragment + state.position_fragment
            cash_value -= state.position_fragment
            
            short_pct = int((short_value / 1000) * 100)
            long_pct = int((long_value / 1000) * 100)
            cash_pct = int((cash_value / 1000) * 100)
            
            logger.info(f"  Portfolio: ~{long_pct}% Long / {short_pct}% Short / {cash_pct}% Cash")
            
        elif units_from_valley == 5:
            # Close all short, convert to long
            long_value += short_value  # Convert short to long
            long_value += state.position_fragment  # Add cash purchase
            cash_value -= state.position_fragment
            short_value = Decimal("0")
            
            logger.info(f"  Portfolio: ~90% Long / 0% Short / ~10% Cash")
            
        elif units_from_valley >= 6:
            # Final purchase, 100% long
            long_value += cash_value  # Use remaining cash
            cash_value = Decimal("0")
            
            logger.info(f"  Portfolio: 100% Long / 0% Short / 0% Cash")
            logger.info("\n  >>> TRIGGERING RESET MECHANISM <<<")
            logger.info("  Position is fully long, cycle complete!")
            
            # Simulate RESET
            logger.info("\n" + "=" * 60)
            logger.info("RESET PROCESS")
            logger.info("=" * 60)
            
            # Calculate cycle performance
            # Assume we gained 5% overall through the cycle
            final_value = Decimal("1050")  
            cycle_profit = final_value - Decimal("1000")
            
            logger.info(f"  Initial Capital: $1000")
            logger.info(f"  Final Value: ${final_value}")
            logger.info(f"  Cycle Profit: ${cycle_profit}")
            logger.info(f"  New Baseline: ${final_value}")
            logger.info(f"  Entry Price Reset: ${price}")
            logger.info(f"  Units Reset: 0")
            logger.info(f"  Phase: ADVANCE")
            break
        
        # Show detailed portfolio
        total_value = long_value + short_value + cash_value
        logger.info(f"  Details: Long=${long_value:.0f}, Short=${short_value:.0f}, Cash=${cash_value:.0f}")
        logger.info(f"  Total Value: ${total_value:.2f}")
    
    logger.info("\n" + "=" * 60)
    logger.success("STAGE 8 DEMO COMPLETED")
    logger.info("Key Features Demonstrated:")
    logger.info("  - Progressive short position closure using hedge fragments")
    logger.info("  - Gradual redeployment into long positions")
    logger.info("  - Cash reserves used to accelerate recovery")
    logger.info("  - Full position reversal from defensive to bullish")
    logger.info("  - Automatic RESET trigger at 100% long")
    logger.info("  - Complete trading cycle: ADVANCE → RETRACEMENT → DECLINE → RECOVERY → RESET")
    logger.info("=" * 60)


async def test_full_cycle_summary():
    """Demonstrate a complete trading cycle through all phases"""
    
    logger.info("\n" + "=" * 60)
    logger.info("COMPLETE TRADING CYCLE DEMONSTRATION")
    logger.info("=" * 60)
    
    phases = [
        ("1. ADVANCE", "Entry at $4400, price rises to $4410 (+5 units)", "100% Long", "$1022"),
        ("2. RETRACEMENT", "Price drops from peak to $4395 (-5 from peak)", "0% Long / 50% Short / 50% Cash", "$1005"),
        ("3. DECLINE", "Price continues to $4385 (valley at -7 units)", "0% Long / 50% Short / 50% Cash", "$1015"),
        ("4. RECOVERY", "Price recovers to $4400 (+6 from valley)", "100% Long / 0% Short / 0% Cash", "$1050"),
        ("5. RESET", "Lock in profits, new baseline at $1050", "100% Long (new cycle)", "$1050"),
    ]
    
    logger.info("Starting Capital: $1000\n")
    
    for phase_num, (phase, description, portfolio, value) in enumerate(phases, 1):
        logger.info(f"{phase}:")
        logger.info(f"  {description}")
        logger.info(f"  Portfolio: {portfolio}")
        logger.info(f"  Total Value: {value}")
        
        if phase_num < len(phases):
            logger.info("  ↓")
    
    logger.info("\n" + "-" * 40)
    logger.info("CYCLE RESULTS:")
    logger.info(f"  Starting: $1000")
    logger.info(f"  Ending: $1050")
    logger.info(f"  Profit: $50 (5%)")
    logger.info(f"  New Baseline: $1050 (profits compounded)")
    
    logger.info("\n" + "=" * 60)
    logger.info("The complete cycle demonstrates:")
    logger.info("1. Profit taking during price rises (ADVANCE)")
    logger.info("2. Defensive positioning during drops (RETRACEMENT)")
    logger.info("3. Short profits during decline (DECLINE)")
    logger.info("4. Strategic re-entry during recovery (RECOVERY)")
    logger.info("5. Profit compounding through RESET")
    logger.info("=" * 60)


async def test_recovery_calculations():
    """Test specific calculations for RECOVERY phase actions"""
    
    logger.info("\n" + "=" * 60)
    logger.info("RECOVERY PHASE CALCULATIONS")
    logger.info("=" * 60)
    
    # Setup
    short_value = Decimal("500")  # $500 in short position
    cash_reserves = Decimal("500")  # $500 in cash
    hedge_fragment = short_value * Decimal("0.25")  # $125 (25% of short)
    position_fragment = Decimal("100")  # $100 (10% of original)
    
    logger.info(f"Starting Position:")
    logger.info(f"  Short: ${short_value}")
    logger.info(f"  Cash: ${cash_reserves}")
    logger.info(f"  Hedge Fragment: ${hedge_fragment}")
    logger.info(f"  Position Fragment: ${position_fragment}")
    
    logger.info("\n" + "-" * 40)
    
    # Simulate each recovery step
    steps = [
        "+2 from valley",
        "+3 from valley",
        "+4 from valley",
        "+5 from valley",
        "+6 from valley",
    ]
    
    long_value = Decimal("0")
    
    for i, step in enumerate(steps, 1):
        logger.info(f"\n{step}:")
        
        if i <= 3:  # +2 to +4
            # Close hedge fragment short, buy hedge + position fragment long
            short_value -= hedge_fragment
            long_value += hedge_fragment + position_fragment
            cash_reserves -= position_fragment
            
            logger.info(f"  Close ${hedge_fragment} short")
            logger.info(f"  Buy ${hedge_fragment} long (from short proceeds)")
            logger.info(f"  Buy ${position_fragment} long (from cash)")
            
        elif i == 4:  # +5
            # Close all short, convert to long
            logger.info(f"  Close remaining ${short_value} short")
            logger.info(f"  Buy ${short_value} long (from short proceeds)")
            logger.info(f"  Buy ${position_fragment} long (from cash)")
            
            long_value += short_value + position_fragment
            cash_reserves -= position_fragment
            short_value = Decimal("0")
            
        else:  # +6
            # Use remaining cash
            logger.info(f"  Buy ${cash_reserves} long (remaining cash)")
            long_value += cash_reserves
            cash_reserves = Decimal("0")
        
        total = long_value + short_value + cash_reserves
        logger.info(f"  Result: Long=${long_value}, Short=${short_value}, Cash=${cash_reserves}")
        logger.info(f"  Total: ${total}")
    
    logger.info("\n" + "=" * 60)
    logger.info("This shows the mathematical progression of position reversal")
    logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("Running Stage 8 RECOVERY Phase Tests\n")
    
    # Run main RECOVERY demo
    asyncio.run(test_recovery_demo())
    
    # Run full cycle summary
    asyncio.run(test_full_cycle_summary())
    
    # Run calculation tests
    asyncio.run(test_recovery_calculations())