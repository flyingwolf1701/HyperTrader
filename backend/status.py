"""
Quick status check for HyperTrader
"""
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.exchange_client import HyperliquidExchangeClient
from src.utils.trade_logger import TradeLogger


def main():
    """Check HyperTrader status"""
    
    print("=" * 60)
    print(f"HYPERTRADER STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize clients
    client = HyperliquidExchangeClient(testnet=True)
    trade_logger = TradeLogger()
    symbol = "ETH/USDC:USDC"
    
    # Account Balance
    balance = client.get_balance("USDC")
    print(f"\nAccount Balance:")
    print(f"  Total: ${balance['total']:.2f} USDC")
    print(f"  Available: ${balance['free']:.2f} USDC")
    print(f"  In Use: ${balance['used']:.2f} USDC")
    
    # Current Position
    position = client.get_position(symbol)
    
    if position:
        current_price = client.get_current_price(symbol)
        position_value = position['contracts'] * current_price
        
        print(f"\nActive Position:")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {position['side'].upper()}")
        print(f"  Size: {position['contracts']:.4f} ETH")
        print(f"  Value: ${position_value:.2f}")
        print(f"  Entry: ${position['entryPrice']:.2f}")
        print(f"  Current: ${current_price:.2f}")
        
        # P&L
        if position['unrealizedPnl'] > 0:
            print(f"  P&L: +${position['unrealizedPnl']:.2f} (+{position['percentage']:.2f}%)")
        else:
            print(f"  P&L: -${abs(position['unrealizedPnl']):.2f} ({position['percentage']:.2f}%)")
    else:
        print("\nNo Active Position")
    
    # Today's Trading Summary
    daily_summary = trade_logger.get_daily_summary()
    if daily_summary["total_trades"] > 0:
        print(f"\nToday's Trading:")
        print(f"  Total Trades: {daily_summary['total_trades']}")
        print(f"  Volume: ${daily_summary['total_volume']:.2f}")
        if daily_summary['realized_pnl'] != 0:
            print(f"  Realized P&L: ${daily_summary['realized_pnl']:.2f}")
        
        if daily_summary.get('trades_by_phase'):
            print(f"  Trades by Phase:")
            for phase, count in daily_summary['trades_by_phase'].items():
                print(f"    {phase}: {count}")
    
    # Current Session Summary
    session_summary = trade_logger.get_session_summary()
    if session_summary["total_trades"] > 0:
        print(f"\nCurrent Session:")
        print(f"  Session ID: {session_summary['session_id']}")
        print(f"  Trades: {session_summary['total_trades']}")
        print(f"  Volume: ${session_summary['total_volume']:.2f}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()