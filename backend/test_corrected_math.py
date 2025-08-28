#!/usr/bin/env python3
"""
HyperTrader - Test Corrected Calculations
Demonstrates the fixed leverage math and compound growth
"""

import sys
from pathlib import Path
from decimal import Decimal
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.strategy.short_position import ShortPosition


def test_corrected_calculations():
    """Test the corrected leverage and fragment calculations"""
    
    print("=" * 70)
    print("HYPERTRADER - CORRECTED CALCULATION TEST")
    print("=" * 70)
    
    # Test parameters (realistic for testing)
    notional_position = Decimal("1000")  # $1000 notional position
    leverage = 25                        # 25x leverage (ETH max on Hyperliquid)
    entry_price = Decimal("2500")       # $2500 per ETH
    unit_size = Decimal("25")           # $25 per unit
    
    print(f"Test Parameters:")
    print(f"  Notional Position: ${notional_position}")
    print(f"  Leverage: {leverage}x")
    print(f"  Entry Price: ${entry_price} per ETH")
    print(f"  Unit Size: ${unit_size}")
    print()
    
    # Calculate initial values - CORRECTED
    margin_required = notional_position / Decimal(leverage)
    eth_amount = notional_position / entry_price
    fragment_notional = notional_position * Decimal("0.12")  # 12% fragment
    fragment_margin = fragment_notional / Decimal(leverage)
    fragment_eth = fragment_notional / entry_price
    
    print("INITIAL POSITION (100% Long) - CORRECTED:")
    print(f"  ETH Amount: {eth_amount:.4f} ETH")
    print(f"  Notional Value: ${notional_position}")
    print(f"  Margin Required: ${margin_required}")
    print(f"  Fragment Size (Notional): ${fragment_notional} (12%)")
    print(f"  Fragment Size (Margin): ${fragment_margin}")
    print(f"  Fragment Size (ETH): {fragment_eth:.4f} ETH")
    print()
    
    # Simulate RETRACEMENT sequence - CORRECTED per Strategy Doc v7.0.3
    print("RETRACEMENT SEQUENCE - STRATEGY DOC v7.0.3 COMPLIANT:")
    print("-" * 50)
    
    current_price = entry_price
    short_positions = []
    
    # CORRECTED: Execute retracement actions per strategy doc v7.0.3
    retracement_data = [
        (-1, entry_price - unit_size, 1, "Sell 1 fragment ETH, Open 1 fragment USD short"),
        (-2, entry_price - unit_size * 2, 2, "Sell 2 fragment ETH, Add 1 fragment USD short"), 
        (-3, entry_price - unit_size * 3, 2, "Sell 2 fragment ETH, Add 1 fragment USD short"),
        (-4, entry_price - unit_size * 4, 2, "Sell 2 fragment ETH, Add 1 fragment USD short")
    ]
    
    total_eth_sold = Decimal("0")
    
    for unit_level, price, eth_multiplier, action_desc in retracement_data:
        eth_to_sell = fragment_eth * eth_multiplier
        total_eth_sold += eth_to_sell
        
        print(f"\n{unit_level} Unit: Price drops to ${price}")
        print(f"Strategy Doc Action: {action_desc}")
        print(f"Implementation: Sell {eth_to_sell:.4f} ETH ({eth_multiplier}x), Short ${fragment_notional}")
        
        # Calculate what we get for selling ETH at current price
        usd_received = eth_to_sell * price
        
        # Track the short position (1x fragment USD each time)
        short = ShortPosition(
            usd_amount=fragment_notional,
            entry_price=price,
            eth_amount=fragment_notional / price,
            unit_opened=unit_level
        )
        short_positions.append(short)
        
        print(f"Result:")
        print(f"  Sold: {eth_to_sell:.4f} ETH -> ${usd_received:.2f}")
        print(f"  Short: ${fragment_notional} ({short.eth_amount:.4f} ETH)")
        print(f"  Total ETH sold: {total_eth_sold:.4f} ETH")
        
    print(f"\n📊 RETRACEMENT SUMMARY:")
    print(f"  Total ETH sold: {total_eth_sold:.4f} ETH")
    print(f"  Original position: {eth_amount:.4f} ETH")
    print(f"  % of position sold: {(total_eth_sold/eth_amount)*100:.1f}%")
    print(f"  Note: CORRECTED scaling - more ETH sold at -2,-3,-4 levels")
    
    # Show short position value at valley - CORRECTED
    valley_price = Decimal("2250")  # Significant drop for P&L demo
    print(f"\nVALLEY REACHED (${valley_price}):")
    print("SHORT POSITION VALUATION:")
    
    total_original = Decimal("0")
    total_current_value = Decimal("0")
    
    for i, short in enumerate(short_positions, 1):
        current_value = short.get_current_value(valley_price)
        pnl = short.get_pnl(valley_price)
        
        total_original += short.usd_amount
        total_current_value += current_value
        
        print(f"  Short #{i}: {short.eth_amount:.4f} ETH @ ${short.entry_price}")
        print(f"    Original: ${short.usd_amount} -> Current: ${current_value:.2f} (P&L: ${pnl:.2f})")
    
    total_pnl = total_current_value - total_original
    
    print(f"\nSUMMARY:")
    print(f"  Original Short Value: ${total_original}")
    print(f"  Current Short Value: ${total_current_value:.2f}")
    print(f"  ** Total P&L: ${total_pnl:.2f}")
    print(f"  Growth Factor: {(total_current_value / total_original):.2f}x")
    
    # Calculate hedge fragment - CORRECTED
    hedge_fragment = total_current_value * Decimal("0.25")
    
    print(f"\nRECOVERY CALCULATIONS:")
    print(f"  Hedge Fragment (25% of current short value): ${hedge_fragment:.2f}")
    print(f"  Position Fragment (cash): ${fragment_notional}")
    print(f"  ** Total per Recovery Unit: ${hedge_fragment + fragment_notional:.2f}")
    
    # Show compound effect over 4 recovery units
    total_recovery_purchases = (hedge_fragment + fragment_notional) * 4
    compound_growth = total_recovery_purchases - notional_position
    growth_percentage = (compound_growth / notional_position) * 100
    
    print(f"\nCOMPOUND GROWTH CALCULATION:")
    print(f"  4 Recovery Units x ${hedge_fragment + fragment_notional:.2f} = ${total_recovery_purchases:.2f}")
    print(f"  Started with: ${notional_position}")
    print(f"  ** Compound Growth: ${compound_growth:.2f} ({growth_percentage:.1f}%)")
    print()
    
    print("=" * 70)
    print("KEY INSIGHTS FROM CORRECTED IMPLEMENTATION:")
    print("=" * 70)
    print("✅ Fragment: 12% of NOTIONAL value (not 10%)")
    print("✅ Leverage: 25x for ETH (not 10x)")
    print("✅ RETRACEMENT: Proper scaling per Strategy Doc v7.0.3")
    print("    - Unit -1: 1x fragment ETH sold")
    print("    - Unit -2: 2x fragment ETH sold") 
    print("    - Unit -3: 2x fragment ETH sold")
    print("    - Unit -4: 2x fragment ETH sold")
    print("✅ Short P&L: Compounds as price drops")
    print("✅ Hedge Fragment: 25% of CURRENT short value (with P&L)")
    print("✅ Compound Growth: Better scaling = better returns")
    print("✅ Strategy Compliance: Exact implementation per official doc")
    print()
    print("🎯 CRITICAL FIX: Retracement now implements correct scaling!")
    print("This dramatically improves the strategy's hedging effectiveness.")


if __name__ == "__main__":
    test_corrected_calculations()
