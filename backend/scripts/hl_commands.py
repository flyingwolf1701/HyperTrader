#!/usr/bin/env python3
"""
Hyperliquid SDK Commands - CLI interface using the HyperliquidClient SDK
"""

import argparse
import sys
from decimal import Decimal
from loguru import logger

# Import SDK
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.exchange.hyperliquid_sdk import HyperliquidClient


def cmd_status(sub_wallet=False):
    """Display account status"""
    try:
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=sub_wallet)
        
        logger.info("=" * 60)
        logger.info("ACCOUNT STATUS")
        logger.info("=" * 60)
        
        # Get balance
        balance = client.get_balance()
        logger.info("Account Balance:")
        logger.info(f"  Total Value: ${balance.total_value:.2f}")
        logger.info(f"  Margin Used: ${balance.margin_used:.2f}")
        logger.info(f"  Available: ${balance.available:.2f}")
        
        # Get positions
        positions = client.get_positions()
        
        logger.info("\nPositions:")
        if positions:
            for symbol, position in positions.items():
                logger.info(f"  {symbol}: {position.side}")
                logger.info(f"    Size: {position.size:.6f} {symbol}")
                logger.info(f"    Entry: ${position.entry_price:.2f}")
                logger.info(f"    Unrealized PnL: ${position.unrealized_pnl:.2f}")
        else:
            logger.info("  No open positions")
            
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        sys.exit(1)


def cmd_trade(symbol: str, amount: float, leverage: int = 10, short: bool = False, sub_wallet: bool = False):
    """Open a trade position"""
    try:
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=sub_wallet)
        
        logger.info("=" * 60)
        logger.info(f"OPENING {'SHORT' if short else 'LONG'} TRADE")
        logger.info("=" * 60)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Position Size: ${amount}")
        logger.info(f"Leverage: {leverage}x")
        logger.info(f"Direction: {'SHORT' if short else 'LONG'}")
        logger.info("=" * 60)
        
        # Get current price for display
        current_price = client.get_current_price(symbol)
        logger.info(f"Current Price: ${current_price:.2f}")
        
        # Open position
        result = client.open_position(
            symbol=symbol,
            usd_amount=Decimal(str(amount)),
            is_long=not short,
            leverage=leverage,
            slippage=0.01
        )
        
        if result.success:
            logger.success("=" * 60)
            logger.success("TRADE OPENED SUCCESSFULLY")
            logger.success(f"Order ID: {result.order_id}")
            logger.success(f"Filled Size: {result.filled_size} {symbol}")
            logger.success(f"Average Price: ${result.average_price}")
            logger.success("=" * 60)
        else:
            logger.error(f"Trade failed: {result.error_message}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to open trade: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_close(symbol: str, sub_wallet: bool = False):
    """Close position for a symbol"""
    try:
        # Import with proper path
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.exchange.wallet_config import WalletConfig

        # Load wallet config
        config = WalletConfig.from_env()

        # Initialize client with new interface
        client = HyperliquidClient(
            config=config,
            wallet_type="sub" if sub_wallet else "main",
            use_testnet=True
        )

        logger.info("=" * 60)
        logger.info("CLOSING POSITION AND ORDERS")
        logger.info("=" * 60)

        # Cancel all open orders first
        logger.info(f"Cancelling all open orders for {symbol}...")
        cancelled_count = client.cancel_all_orders(symbol)
        if cancelled_count > 0:
            logger.info(f"✅ Cancelled {cancelled_count} orders")
        else:
            logger.info("No orders to cancel")

        # Check if position exists
        position = client.get_position(symbol)
        if not position:
            logger.info(f"No position to close for {symbol}")
            return

        logger.info(f"Closing {position.side} position")
        logger.info(f"Size: {position.size:.6f} {symbol}")

        # Close the position
        result = client.close_position(symbol)

        if result.success:
            logger.success("✅ Position closed successfully")
            logger.success(f"Closed at average price: ${result.average_price}")
        else:
            logger.error(f"❌ Failed to close position: {result.error_message}")

    except Exception as e:
        logger.error(f"Failed to close position: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Hyperliquid SDK Trading Commands")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show account status')
    status_parser.add_argument('--sub-wallet', action='store_true', help='Use sub-wallet account')
    
    # Trade command
    trade_parser = subparsers.add_parser('trade', help='Open a trade position')
    trade_parser.add_argument('symbol', type=str, help='Trading symbol (e.g., ETH)')
    trade_parser.add_argument('amount', type=float, help='Position size in USD')
    trade_parser.add_argument('--leverage', type=int, default=10, help='Leverage (default: 10)')
    trade_parser.add_argument('--short', action='store_true', help='Open a short position instead of long')
    trade_parser.add_argument('--sub-wallet', action='store_true', help='Trade on sub-wallet account')
    
    # Close command
    close_parser = subparsers.add_parser('close', help='Close a position')
    close_parser.add_argument('symbol', type=str, help='Symbol to close (e.g., ETH)')
    close_parser.add_argument('--sub-wallet', action='store_true', help='Close position on sub-wallet')
    
    args = parser.parse_args()
    
    if args.command == 'status':
        cmd_status(args.sub_wallet)
    elif args.command == 'trade':
        cmd_trade(args.symbol, args.amount, args.leverage, args.short, args.sub_wallet)
    elif args.command == 'close':
        cmd_close(args.symbol, args.sub_wallet)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()