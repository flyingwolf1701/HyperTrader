"""
Stage 6 Test: RESET Mechanism
Tests strategy re-calibration after completing a full cycle
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


async def test_reset_demo():
    """Test Stage 6 RESET mechanism without real trades"""
    
    logger.info("=" * 60)
    logger.info("STAGE 6 DEMO: RESET Mechanism")
    logger.info("=" * 60)
    
    # Simulate a strategy that has completed a full cycle
    state = StrategyState(
        symbol="ETH/USDC:USDC",
        position_size_usd=Decimal("1000"),  # Started with $1000
        unit_size=Decimal("2.0"),
        leverage=10
    )
    
    # Simulate we've been through a complete cycle
    # Started at $4400, went up to $4410 (+5 units), down to $4390 (-5 units), 
    # and recovered back to $4420 (+10 units)
    state.has_position = True
    state.entry_price = Decimal("4400.00")  # Original entry
    state.unit_tracker.entry_price = state.entry_price
    
    # Simulate the journey:
    # - ADVANCE: Price went up to peak (+5 units = $4410)
    # - RETRACEMENT: Price dropped to -5 from peak 
    # - DECLINE: Price continued down to valley (-5 units = $4390)
    # - RECOVERY: Price recovered to +10 units from valley (now at $4420)
    
    # Current state after full cycle
    current_price = Decimal("4420.00")  # +20 from original entry
    state.unit_tracker.current_unit = 10  # Current position in units
    state.unit_tracker.peak_unit = 5  # Historical peak during ADVANCE
    state.unit_tracker.valley_unit = -5  # Historical valley during DECLINE
    state.unit_tracker.phase = Phase.RECOVERY  # Just completed recovery
    
    # Position has grown due to successful cycle
    # Assume 20% profit from the cycle
    state.position_allocation = Decimal("1200.00")  # Position grew to $1200
    state.initial_position_allocation = Decimal("1000.00")  # Started with $1000
    state.calculate_position_fragment()
    
    logger.info("Pre-RESET Status (After Full Cycle):")
    logger.info(f"  Original Entry: ${state.entry_price}")
    logger.info(f"  Current Price: ${current_price}")
    logger.info(f"  Phase: {state.unit_tracker.phase.value}")
    logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
    logger.info(f"  Peak Unit (historical): {state.unit_tracker.peak_unit}")
    logger.info(f"  Valley Unit (historical): {state.unit_tracker.valley_unit}")
    logger.info(f"  Initial Position: ${state.initial_position_allocation}")
    logger.info(f"  Current Position Value: ${state.position_allocation}")
    logger.info(f"  Cycle Profit: ${state.position_allocation - state.initial_position_allocation}")
    
    logger.info("\n" + "=" * 60)
    logger.info("TRIGGERING RESET MECHANISM")
    logger.info("=" * 60)
    
    # Simulate RESET
    logger.info("\nRESET Process:")
    
    # 1. Calculate cycle performance
    cycle_pnl = state.position_allocation - state.initial_position_allocation
    cycle_pnl_pct = (cycle_pnl / state.initial_position_allocation) * Decimal("100")
    
    logger.info(f"1. Cycle Summary:")
    logger.info(f"   Starting Value: ${state.initial_position_allocation}")
    logger.info(f"   Ending Value: ${state.position_allocation}")
    logger.info(f"   Cycle P&L: ${cycle_pnl:.2f} ({cycle_pnl_pct:.2f}%)")
    
    # 2. Update baseline - THIS IS THE KEY PART
    state.pre_reset_value = state.position_allocation
    state.position_allocation = Decimal("1200.00")  # Lock in the gains
    state.initial_position_allocation = Decimal("1200.00")  # New baseline!
    
    logger.info(f"\n2. Lock in Profits:")
    logger.info(f"   New Baseline Position: ${state.initial_position_allocation}")
    logger.info(f"   Previous Baseline: $1000.00")
    logger.info(f"   Profits Compounded: ${cycle_pnl:.2f}")
    
    # 3. Reset all unit tracking
    state.unit_tracker.current_unit = 0
    state.unit_tracker.peak_unit = 0
    state.unit_tracker.valley_unit = 0
    state.entry_price = current_price  # Current price becomes new entry
    state.unit_tracker.entry_price = current_price
    
    logger.info(f"\n3. Reset Unit Tracking:")
    logger.info(f"   Current Unit: {state.unit_tracker.current_unit} (reset to 0)")
    logger.info(f"   Peak Unit: {state.unit_tracker.peak_unit} (reset to 0)")
    logger.info(f"   Valley Unit: {state.unit_tracker.valley_unit} (reset to 0)")
    logger.info(f"   New Entry Price: ${state.entry_price}")
    
    # 4. Recalculate fragments
    state.calculate_position_fragment()
    
    logger.info(f"\n4. Recalculate Fragments:")
    logger.info(f"   New Position Fragment: ${state.position_fragment:.2f}")
    logger.info(f"   (10% of ${state.position_allocation})")
    
    # 5. Enter ADVANCE phase
    state.unit_tracker.phase = Phase.ADVANCE
    state.reset_count = 1
    
    logger.info(f"\n5. Enter New Cycle:")
    logger.info(f"   Phase: {state.unit_tracker.phase.value}")
    logger.info(f"   Reset Count: {state.reset_count}")
    
    logger.info("\n" + "=" * 60)
    logger.info("POST-RESET STATUS")
    logger.info("=" * 60)
    
    logger.info("New Cycle Starting Point:")
    logger.info(f"  Position Value: ${state.position_allocation}")
    logger.info(f"  Entry Price: ${state.entry_price}")
    logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
    logger.info(f"  Phase: {state.unit_tracker.phase.value}")
    logger.info(f"  Position Fragment: ${state.position_fragment:.2f}")
    logger.info(f"  Total Resets: {state.reset_count}")
    
    # Simulate next cycle starting
    logger.info("\n" + "=" * 60)
    logger.info("SIMULATING NEXT CYCLE START")
    logger.info("=" * 60)
    
    # Price moves up by 2 units
    new_price = state.entry_price + (state.unit_size * 2)  # $4424
    state.unit_tracker.calculate_unit_change(new_price)
    
    # Position value grows
    price_change_pct = (new_price - state.entry_price) / state.entry_price
    state.position_allocation = state.initial_position_allocation * (Decimal("1") + price_change_pct)
    state.calculate_position_fragment()
    
    logger.info(f"\nPrice moves to ${new_price} (+2 units from new baseline):")
    logger.info(f"  Current Unit: {state.unit_tracker.current_unit}")
    logger.info(f"  Peak Unit: {state.unit_tracker.peak_unit}")
    logger.info(f"  Position Value: ${state.position_allocation:.2f}")
    logger.info(f"  Position Fragment: ${state.position_fragment:.2f}")
    logger.info(f"  Growth from new baseline: ${state.position_allocation - state.initial_position_allocation:.2f}")
    
    logger.info("\n" + "=" * 60)
    logger.success("STAGE 6 DEMO COMPLETED")
    logger.info("Key Features Demonstrated:")
    logger.info("  - Cycle P&L calculation before reset")
    logger.info("  - Profits locked into new baseline ($1000 -> $1200)")
    logger.info("  - All unit variables reset to 0")
    logger.info("  - Entry price updated to current market price")
    logger.info("  - Position fragments recalculated based on new value")
    logger.info("  - Strategy enters ADVANCE phase with compounded position")
    logger.info("  - Next cycle builds on the increased capital base")
    logger.info("=" * 60)


async def test_multiple_resets():
    """Demonstrate multiple RESET cycles compounding profits"""
    
    logger.info("\n" + "=" * 60)
    logger.info("MULTIPLE RESET DEMONSTRATION")
    logger.info("=" * 60)
    
    initial_capital = Decimal("1000")
    position_value = initial_capital
    
    # Simulate 5 successful cycles with 15% profit each
    cycles = [
        ("Cycle 1", Decimal("0.15")),
        ("Cycle 2", Decimal("0.12")),
        ("Cycle 3", Decimal("0.18")),
        ("Cycle 4", Decimal("0.10")),
        ("Cycle 5", Decimal("0.20")),
    ]
    
    logger.info(f"Starting Capital: ${initial_capital}")
    logger.info("\nSimulating 5 trading cycles:\n")
    
    total_resets = 0
    
    for cycle_name, profit_pct in cycles:
        cycle_profit = position_value * profit_pct
        new_value = position_value + cycle_profit
        
        logger.info(f"{cycle_name}:")
        logger.info(f"  Start: ${position_value:.2f}")
        logger.info(f"  Profit: ${cycle_profit:.2f} ({profit_pct * 100:.0f}%)")
        logger.info(f"  End: ${new_value:.2f}")
        logger.info(f"  >>> RESET: Lock in ${new_value:.2f} as new baseline")
        
        position_value = new_value
        total_resets += 1
    
    total_profit = position_value - initial_capital
    total_return = (total_profit / initial_capital) * Decimal("100")
    
    logger.info("\n" + "-" * 40)
    logger.info("FINAL RESULTS:")
    logger.info(f"  Initial Capital: ${initial_capital}")
    logger.info(f"  Final Capital: ${position_value:.2f}")
    logger.info(f"  Total Profit: ${total_profit:.2f}")
    logger.info(f"  Total Return: {total_return:.2f}%")
    logger.info(f"  Total Resets: {total_resets}")
    logger.info(f"  Average per Cycle: {total_return / total_resets:.2f}%")
    
    logger.info("\n" + "=" * 60)
    logger.info("This demonstrates the power of the RESET mechanism:")
    logger.info("- Each cycle's profits become the baseline for the next")
    logger.info("- Compounding effect significantly increases returns")
    logger.info("- Strategy adapts to new capital levels automatically")
    logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("Running Stage 6 RESET Mechanism Tests\n")
    
    # Run main RESET demo
    asyncio.run(test_reset_demo())
    
    # Run multiple resets demo
    asyncio.run(test_multiple_resets())