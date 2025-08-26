"""
Real-time HyperTrader monitoring dashboard
"""
import sys
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient


def format_pnl(pnl: Decimal, percentage: Decimal) -> str:
    """Format P&L with color indicators"""
    if pnl > 0:
        return f"+${pnl:.2f} (+{percentage:.2f}%)"
    elif pnl < 0:
        return f"-${abs(pnl):.2f} ({percentage:.2f}%)"
    else:
        return f"${pnl:.2f} ({percentage:.2f}%)"


def main():
    """Monitor HyperTrader status in real-time"""
    
    client = HyperliquidExchangeClient(testnet=True)
    symbol = "ETH/USDC:USDC"
    
    logger.info("Starting HyperTrader Monitor")
    logger.info("Press Ctrl+C to stop")
    print("\n" + "="*60)
    
    try:
        while True:
            # Clear previous output (platform-agnostic)
            print("\033[2J\033[H", end="")  # Clear screen and move cursor to top
            
            # Header
            print("="*60)
            print(f"HYPERTRADER MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*60)
            
            # Get balance
            balance = client.get_balance("USDC")
            print(f"\nAccount Balance: ${balance['free']:.2f} USDC")
            print(f"  Available: ${balance['free']:.2f}")
            print(f"  In Use: ${balance['used']:.2f}")
            
            # Get position
            position = client.get_position(symbol)
            
            if position:
                # Get current price
                current_price = client.get_current_price(symbol)
                
                print(f"\nActive Position:")
                print(f"  Symbol: {symbol}")
                print(f"  Side: {position['side'].upper()}")
                print(f"  Size: {position['contracts']:.4f} ETH")
                print(f"  Entry Price: ${position['entryPrice']:.2f}")
                print(f"  Current Price: ${current_price:.2f}")
                
                # Calculate position value
                position_value = position['contracts'] * current_price
                print(f"  Position Value: ${position_value:.2f}")
                
                # P&L
                pnl_str = format_pnl(position['unrealizedPnl'], position['percentage'])
                print(f"  Unrealized P&L: {pnl_str}")
                
                # Price movement
                price_change = current_price - position['entryPrice'] if position['entryPrice'] else 0
                price_change_pct = (price_change / position['entryPrice'] * 100) if position['entryPrice'] else 0
                
                print(f"\nPrice Movement:")
                print(f"  Change: ${price_change:.2f} ({price_change_pct:+.2f}%)")
                
                # Unit tracking (approximate based on $2 units)
                units_moved = int(abs(price_change) / 2)
                print(f"  Units Moved: {units_moved} (at $2/unit)")
                
            else:
                print("\nNo Active Position")
                print("  Strategy may be waiting for entry signal")
            
            # Check all positions
            try:
                all_positions = client.exchange.fetch_positions()
                active_count = sum(1 for pos in all_positions if float(pos.get('contracts', 0)) != 0)
                if active_count > 1:
                    print(f"\nWarning: {active_count} active positions detected!")
            except:
                pass
            
            print("\n" + "-"*60)
            print("Refreshing in 5 seconds...")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
        logger.info("Monitor shutdown")
    except Exception as e:
        logger.error(f"Monitor error: {e}")
        raise


if __name__ == "__main__":
    main()