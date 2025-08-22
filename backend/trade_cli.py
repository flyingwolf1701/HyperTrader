#!/usr/bin/env python3
"""
HyperTrader CLI Tool
Simple command-line interface to start and monitor trades.
"""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Optional
import aiohttp
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class TradeCLI:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        
    async def create_trading_plan(self, symbol: str, position_size: float, leverage: int = 10):
        """Create a new trading plan via API"""
        url = f"{self.base_url}/api/v1/trade/start"
        
        payload = {
            "symbol": symbol,
            "position_size": position_size,
            "leverage": leverage
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ Trading plan created successfully!")
                        print(f"   Plan ID: {result['plan_id']}")
                        print(f"   Symbol: {result['symbol']}")
                        print(f"   Entry Price: ${result['entry_price']}")
                        print(f"   Position Size: ${result['position_size']}")
                        print(f"   Margin Required: ${result['initial_margin']}")
                        print(f"   Order ID: {result['order_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create trading plan: {response.status}")
                        print(f"   Error: {error_text}")
                        return None
            except Exception as e:
                print(f"❌ Connection error: {e}")
                return None
    
    async def get_trading_state(self, symbol: str):
        """Get current trading state for a symbol"""
        url = f"{self.base_url}/api/v1/trade/state/{symbol}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to get trading state: {response.status}")
                        print(f"   Error: {error_text}")
                        return None
            except Exception as e:
                print(f"❌ Connection error: {e}")
                return None
    
    async def get_current_price(self, symbol: str):
        """Get current market price"""
        url = f"{self.base_url}/api/v1/exchange/price/{symbol}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['price']
                    else:
                        return None
            except Exception as e:
                return None
    
    async def monitor_trading(self, symbol: str, interval: int = 5):
        """Monitor a trading plan in real-time"""
        print(f"🔍 Monitoring {symbol} trading plan...")
        print("   Press Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                # Get current state
                state = await self.get_trading_state(symbol)
                if not state:
                    print(f"❌ No active trading plan found for {symbol}")
                    break
                
                # Get current price
                current_price = await self.get_current_price(symbol)
                
                # Display status
                system_state = state['system_state']
                print(f"\r📊 {symbol} Monitor [{system_state['current_phase'].upper()}]", end="")
                print(f" | Price: ${current_price:.2f}" if current_price else " | Price: N/A", end="")
                print(f" | Unit: {system_state['current_unit']}", end="")
                print(f" | Long: ${float(system_state['long_invested']):.2f}", end="")
                print(f" | Hedge: ${float(system_state['hedge_long']):.2f}/${float(system_state['hedge_short']):.2f}", end="", flush=True)
                
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n✋ Stopped monitoring {symbol}")
    
    def print_help(self):
        """Print usage help"""
        print("""
🚀 HyperTrader CLI Tool

Usage:
  python trade_cli.py create <SYMBOL> <POSITION_SIZE> [--leverage N]
  python trade_cli.py monitor <SYMBOL> [--interval N]
  python trade_cli.py status <SYMBOL>
  
Examples:
  python trade_cli.py create ETH 1000 --leverage 10    # $1000 position ($100 margin)
  python trade_cli.py create BTC 500 --leverage 5      # $500 position ($100 margin)
  python trade_cli.py monitor ETH --interval 3
  python trade_cli.py status ETH

Commands:
  create   - Create a new trading plan and place initial order
           - POSITION_SIZE is the USD value you want to trade
           - Margin required = POSITION_SIZE / LEVERAGE
  monitor  - Monitor an active trading plan in real-time
  status   - Get current status of a trading plan
  
Options:
  --leverage N   - Set leverage (default: 10)
  --interval N   - Monitoring interval in seconds (default: 5)
        """)

async def main():
    parser = argparse.ArgumentParser(description="HyperTrader CLI Tool")
    parser.add_argument('command', choices=['create', 'monitor', 'status', 'help'], 
                       help='Command to execute')
    parser.add_argument('symbol', nargs='?', help='Trading symbol (e.g., ETH)')
    parser.add_argument('position_size', type=float, nargs='?', help='USD position size to trade')
    parser.add_argument('--leverage', type=int, default=10, help='Leverage (default: 10)')
    parser.add_argument('--interval', type=int, default=5, help='Monitor interval (default: 5s)')
    parser.add_argument('--url', default='http://localhost:8000', help='Backend URL')
    
    args = parser.parse_args()
    
    cli = TradeCLI(base_url=args.url)
    
    if args.command == 'help':
        cli.print_help()
        return
    
    if args.command == 'create':
        if not args.symbol or args.position_size is None:
            print("❌ Error: create command requires <SYMBOL> and <POSITION_SIZE>")
            print("   Example: python trade_cli.py create ETH 1000 --leverage 10")
            print("   This creates a $1000 ETH position requiring $100 margin at 10x leverage")
            return
        
        result = await cli.create_trading_plan(args.symbol, args.position_size, args.leverage)
        if result:
            print(f"\n🎯 Ready to monitor! Run: python trade_cli.py monitor {args.symbol}")
    
    elif args.command == 'monitor':
        if not args.symbol:
            print("❌ Error: monitor command requires <SYMBOL>")
            print("   Example: python trade_cli.py monitor ETH")
            return
        
        await cli.monitor_trading(args.symbol, args.interval)
    
    elif args.command == 'status':
        if not args.symbol:
            print("❌ Error: status command requires <SYMBOL>")
            print("   Example: python trade_cli.py status ETH")
            return
        
        state = await cli.get_trading_state(args.symbol)
        if state:
            system_state = state['system_state']
            print(f"📈 Trading Plan Status for {args.symbol}")
            print(f"   Phase: {system_state['current_phase'].upper()}")
            print(f"   Current Unit: {system_state['current_unit']}")
            print(f"   Entry Price: ${float(system_state['entry_price']):.2f}")
            print(f"   Long Invested: ${float(system_state['long_invested']):.2f}")
            print(f"   Long Cash: ${float(system_state['long_cash']):.2f}")
            print(f"   Hedge Long: ${float(system_state['hedge_long']):.2f}")
            print(f"   Hedge Short: ${float(system_state['hedge_short']):.2f}")

if __name__ == "__main__":
    asyncio.run(main())