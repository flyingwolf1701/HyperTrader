"""
Stage 7 Test: DECLINE Phase
Tests short position management during continued price decline
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


async def test_decline_demo():
    """Test Stage 7 DECLINE phase without real trades"""
    
    logger.info("=" * 60)
    logger.info("STAGE 7 DEMO: DECLINE Phase")
    logger.info("=" * 60)
    
    # Create a strategy in DECLINE phase
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),
        unit_size=Decimal("2.0"),
        leverage=10
    )
    
    # Simulate we've gone through RETRACEMENT and are now in DECLINE
    # Entry was at $4400, peak was at +3 units ($4406)
    # We went through full RETRACEMENT to -6 from peak
    # Now at $4394 (-3 units from original entry)
    
    state.has_position = True
    state.entry_price = Decimal("4400.00")  # Original entry
    state.unit_tracker.entry_price = state.entry_price
    state.unit_tracker.phase = Phase.DECLINE
    
    # Current state
    current_price = Decimal("4394.00")  # -3 units from entry
    state.unit_tracker.current_unit = -3
    state.unit_tracker.peak_unit = 3  # Historical peak
    state.unit_tracker.valley_unit = -3  # Current valley
    
    # Portfolio is now ~50% short, ~50% cash (after RETRACEMENT)
    # Short position entered around $4404 (average)
    short_entry_price = Decimal("4404.00")
    short_position_size = state.position_size_usd * Decimal("0.5")  # 50% in short
    short_contracts = short_position_size / short_entry_price
    
    logger.info("Starting Position (entering DECLINE):")
    logger.info(f"  Original Entry: ${state.entry_price}")
    logger.info(f"  Current Price: ${current_price}")
    logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
    logger.info(f"  Valley Unit: {state.unit_tracker.valley_unit}")
    logger.info(f"  Short Entry: ${short_entry_price}")
    logger.info(f"  Short Size: ${short_position_size} ({short_contracts:.6f} ETH)")
    logger.info(f"  Portfolio: ~50% Short / ~50% Cash")
    
    # Calculate initial short profit
    short_profit = (short_entry_price - current_price) * short_contracts
    logger.info(f"  Short P&L: ${short_profit:.2f}")
    
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATING DECLINE PHASE")
    logger.info("=" * 60)
    
    # Simulate continued price decline
    decline_scenarios = [
        (Decimal("4392.00"), -4, "Price drops to new low"),
        (Decimal("4390.00"), -5, "Further decline"),
        (Decimal("4388.00"), -6, "Deeper valley"),
        (Decimal("4386.00"), -7, "Maximum decline"),
        (Decimal("4388.00"), -6, "Slight recovery (+1 from valley)"),
        (Decimal("4390.00"), -5, "Recovery continues (+2 from valley)"),
    ]
    
    for price, expected_unit, description in decline_scenarios:
        logger.info(f"\n{description}:")
        logger.info(f"  Price: ${price}")
        
        # Update unit tracker
        state.unit_tracker.calculate_unit_change(price)
        
        # Update valley if new low
        if state.unit_tracker.current_unit < state.unit_tracker.valley_unit:
            state.unit_tracker.valley_unit = state.unit_tracker.current_unit
            logger.info(f"  >>> NEW VALLEY: {state.unit_tracker.valley_unit} units")
        
        # Calculate short position value and profit
        short_value = short_contracts * price
        short_profit = (short_entry_price - price) * short_contracts
        short_profit_pct = (short_profit / short_position_size) * Decimal("100")
        
        # Calculate hedge fragment (25% of short value)
        hedge_fragment = short_value * Decimal("0.25")
        
        logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
        logger.info(f"  Valley Unit: {state.unit_tracker.valley_unit}")
        logger.info(f"  Units from Valley: {state.unit_tracker.get_units_from_valley()}")
        logger.info(f"  Short Position Value: ${short_value:.2f}")
        logger.info(f"  Short P&L: ${short_profit:.2f} ({short_profit_pct:.1f}%)")
        logger.info(f"  Hedge Fragment: ${hedge_fragment:.2f}")
        
        # Check for transition to RECOVERY
        if state.unit_tracker.get_units_from_valley() >= 2:
            logger.info("\n" + "=" * 60)
            logger.info(">>> TRIGGERING RECOVERY PHASE <<<")
            logger.info(f"Price has recovered +2 units from valley")
            logger.info("Transitioning from DECLINE to RECOVERY")
            state.unit_tracker.phase = Phase.RECOVERY
            logger.info("Stage 8 will handle gradual position reversal")
            logger.info("=" * 60)
            break
    
    # Summary of DECLINE phase
    logger.info("\n" + "=" * 60)
    logger.info("DECLINE PHASE SUMMARY")
    logger.info("=" * 60)
    
    # Calculate total profit from short during decline
    lowest_price = Decimal("4386.00")
    max_short_profit = (short_entry_price - lowest_price) * short_contracts
    
    logger.info(f"Short Entry Price: ${short_entry_price}")
    logger.info(f"Lowest Price Reached: ${lowest_price}")
    logger.info(f"Maximum Short Profit: ${max_short_profit:.2f}")
    logger.info(f"Valley Unit: {state.unit_tracker.valley_unit}")
    
    # Cash position remains stable
    cash_value = state.position_size_usd * Decimal("0.5")
    total_portfolio = short_value + cash_value + short_profit
    
    logger.info(f"\nFinal Portfolio Value:")
    logger.info(f"  Short Position: ${short_value:.2f}")
    logger.info(f"  Unrealized P&L: ${short_profit:.2f}")
    logger.info(f"  Cash Reserves: ${cash_value:.2f}")
    logger.info(f"  Total Value: ${total_portfolio:.2f}")
    
    original_value = state.position_size_usd
    total_return = ((total_portfolio - original_value) / original_value) * Decimal("100")
    logger.info(f"  Return vs Original: {total_return:.2f}%")
    
    logger.info("\n" + "=" * 60)
    logger.success("STAGE 7 DEMO COMPLETED")
    logger.info("Key Features Demonstrated:")
    logger.info("  - Valley unit tracking for new lows")
    logger.info("  - Short position profit accumulation")
    logger.info("  - Hedge fragment calculation (25% of short value)")
    logger.info("  - Transition trigger at +2 units from valley")
    logger.info("  - Defensive positioning protects capital in downtrends")
    logger.info("=" * 60)


async def test_decline_profit_scenarios():
    """Demonstrate different profit scenarios in DECLINE phase"""
    
    logger.info("\n" + "=" * 60)
    logger.info("DECLINE PHASE PROFIT SCENARIOS")
    logger.info("=" * 60)
    
    scenarios = [
        ("Small Decline", Decimal("10"), Decimal("4400"), Decimal("4390")),
        ("Medium Decline", Decimal("30"), Decimal("4400"), Decimal("4370")),
        ("Large Decline", Decimal("50"), Decimal("4400"), Decimal("4350")),
    ]
    
    for name, decline_amount, entry, bottom in scenarios:
        short_size = Decimal("500")  # $500 in short position
        contracts = short_size / entry
        
        profit = (entry - bottom) * contracts
        profit_pct = (profit / short_size) * Decimal("100")
        
        logger.info(f"\n{name} (${decline_amount} drop):")
        logger.info(f"  Short Entry: ${entry}")
        logger.info(f"  Bottom Price: ${bottom}")
        logger.info(f"  Price Drop: ${decline_amount}")
        logger.info(f"  Short Profit: ${profit:.2f} ({profit_pct:.1f}%)")
        
        # Show how hedge fragment changes
        new_short_value = contracts * bottom
        hedge_fragment = new_short_value * Decimal("0.25")
        logger.info(f"  Hedge Fragment: ${hedge_fragment:.2f}")
    
    logger.info("\n" + "=" * 60)
    logger.info("This shows how the short position protects and profits")
    logger.info("during market downturns, while hedge fragments prepare")
    logger.info("for the eventual recovery phase.")
    logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("Running Stage 7 DECLINE Phase Tests\n")
    
    # Run main DECLINE demo
    asyncio.run(test_decline_demo())
    
    # Run profit scenarios
    asyncio.run(test_decline_profit_scenarios())