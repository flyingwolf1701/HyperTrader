#!/usr/bin/env python3
"""
HyperTrader CLI - Professional trading interface for Hyperliquid
"""

import argparse
import sys
from decimal import Decimal
from typing import Optional
from loguru import logger
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.exchange.hyperliquid_sdk import HyperliquidClient


class TradingCLI:
    """Main CLI application for HyperTrader"""
    
    def __init__(self):
        """Initialize the CLI with default settings"""
        self.client: Optional[HyperliquidClient] = None
        self.use_testnet = True
        self.use_sub_wallet = False
        
    def initialize_client(self, use_testnet: bool = True, use_sub_wallet: bool = False):
        """Initialize or reinitialize the Hyperliquid client"""
        self.use_testnet = use_testnet
        self.use_sub_wallet = use_sub_wallet
        self.client = HyperliquidClient(use_testnet=use_testnet, use_sub_wallet=use_sub_wallet)
        
    def cmd_status(self, args):
        """Display account status and positions"""
        if not self.client:
            self.initialize_client(use_testnet=not args.mainnet, use_sub_wallet=args.sub_wallet)
            
        try:
            logger.info("=" * 60)
            logger.info("ACCOUNT STATUS")
            logger.info("=" * 60)
            
            # Network and wallet info
            network = "TESTNET" if self.use_testnet else "MAINNET"
            wallet_type = "SUB-WALLET" if self.use_sub_wallet else "MAIN WALLET"
            logger.info(f"Network: {network}")
            logger.info(f"Wallet: {wallet_type}")
            logger.info(f"Address: {self.client.trading_wallet_address[:8]}...")
            
            # Get balance
            balance = self.client.get_balance()
            logger.info("\nBalance:")
            logger.info(f"  Total Value: ${balance.total_value:.2f}")
            logger.info(f"  Margin Used: ${balance.margin_used:.2f}")
            logger.info(f"  Available: ${balance.available:.2f}")
            
            # Get positions
            positions = self.client.get_positions()
            
            logger.info("\nPositions:")
            if positions:
                for symbol, position in positions.items():
                    logger.info(f"  {symbol}: {position.side}")
                    logger.info(f"    Size: {position.size:.6f} {symbol}")
                    logger.info(f"    Entry: ${position.entry_price:.2f}")
                    
                    # Get current price for PnL calculation
                    current_price = self.client.get_current_price(symbol)
                    logger.info(f"    Current: ${current_price:.2f}")
                    logger.info(f"    Unrealized PnL: ${position.unrealized_pnl:.2f}")
                    logger.info(f"    Margin Used: ${position.margin_used:.2f}")
            else:
                logger.info("  No open positions")
                
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            sys.exit(1)
    
    def cmd_trade(self, args):
        """Open a new trading position"""
        if not self.client:
            self.initialize_client(use_testnet=not args.mainnet, use_sub_wallet=args.sub_wallet)
            
        try:
            symbol = args.symbol.upper()
            amount = Decimal(str(args.amount))
            leverage = args.leverage
            is_long = not args.short
            
            logger.info("=" * 60)
            logger.info(f"OPENING {'LONG' if is_long else 'SHORT'} POSITION")
            logger.info("=" * 60)
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Amount: ${amount}")
            logger.info(f"Leverage: {leverage}x")
            logger.info(f"Direction: {'LONG' if is_long else 'SHORT'}")
            
            # Confirm for mainnet
            if not self.use_testnet:
                logger.warning("WARNING: Trading on MAINNET with REAL funds!")
                response = input("Type 'YES' to continue: ")
                if response != "YES":
                    logger.info("Trade cancelled")
                    return
            
            # Execute trade
            result = self.client.open_position(
                symbol=symbol,
                usd_amount=amount,
                is_long=is_long,
                leverage=leverage
            )
            
            if result.success:
                logger.success("=" * 60)
                logger.success("TRADE EXECUTED SUCCESSFULLY")
                logger.success(f"Order ID: {result.order_id}")
                logger.success(f"Filled Size: {result.filled_size} {symbol}")
                logger.success(f"Average Price: ${result.average_price}")
                logger.success("=" * 60)
            else:
                logger.error(f"Trade failed: {result.error_message}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Failed to open trade: {e}")
            sys.exit(1)
    
    def cmd_close(self, args):
        """Close an existing position"""
        if not self.client:
            self.initialize_client(use_testnet=not args.mainnet, use_sub_wallet=args.sub_wallet)
            
        try:
            symbol = args.symbol.upper()
            
            # Check if position exists
            position = self.client.get_position(symbol)
            if not position:
                logger.info(f"No position to close for {symbol}")
                return
            
            logger.info("=" * 60)
            logger.info("CLOSING POSITION")
            logger.info("=" * 60)
            logger.info(f"Symbol: {symbol}")
            logger.info(f"Side: {position.side}")
            logger.info(f"Size: {position.size:.6f} {symbol}")
            logger.info(f"Unrealized PnL: ${position.unrealized_pnl:.2f}")
            
            # Confirm closure
            if not args.force:
                response = input("Confirm close position? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Close cancelled")
                    return
            
            # Close position
            result = self.client.close_position(symbol)
            
            if result.success:
                logger.success("=" * 60)
                logger.success("POSITION CLOSED SUCCESSFULLY")
                logger.success(f"Order ID: {result.order_id}")
                logger.success(f"Closed at: ${result.average_price}")
                logger.success("=" * 60)
            else:
                logger.error(f"Failed to close: {result.error_message}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            sys.exit(1)
    
    def cmd_price(self, args):
        """Get current price for a symbol"""
        if not self.client:
            self.initialize_client(use_testnet=not args.mainnet, use_sub_wallet=False)
            
        try:
            symbol = args.symbol.upper()
            price = self.client.get_current_price(symbol)
            
            logger.info(f"{symbol}: ${price:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            sys.exit(1)
    
    def cmd_switch(self, args):
        """Switch between main wallet and sub-wallet"""
        try:
            use_sub = args.wallet == 'sub'
            self.client.switch_wallet(use_sub_wallet=use_sub)
            
            wallet_type = "SUB-WALLET" if use_sub else "MAIN WALLET"
            logger.success(f"Switched to {wallet_type}")
            logger.info(f"Active address: {self.client.trading_wallet_address[:8]}...")
            
        except Exception as e:
            logger.error(f"Failed to switch wallet: {e}")
            sys.exit(1)


def setup_logging(verbose: bool = False):
    """Configure logging with clean output"""
    logger.remove()
    
    # Console logging
    if verbose:
        log_format = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>"
        log_level = "DEBUG"
    else:
        log_format = "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>"
        log_level = "INFO"
    
    logger.add(
        sys.stdout,
        colorize=True,
        format=log_format,
        level=log_level
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="HyperTrader - Professional Hyperliquid Trading CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show account status and positions")
    status_parser.add_argument("--sub-wallet", action="store_true", help="Use sub-wallet")
    
    # Trade command
    trade_parser = subparsers.add_parser("trade", help="Open a trading position")
    trade_parser.add_argument("symbol", help="Trading symbol (e.g., ETH, BTC)")
    trade_parser.add_argument("amount", type=float, help="Position size in USD")
    trade_parser.add_argument("-l", "--leverage", type=int, default=10, help="Leverage (default: 10)")
    trade_parser.add_argument("-s", "--short", action="store_true", help="Open short position")
    trade_parser.add_argument("--sub-wallet", action="store_true", help="Trade on sub-wallet")
    
    # Close command
    close_parser = subparsers.add_parser("close", help="Close a position")
    close_parser.add_argument("symbol", help="Symbol to close (e.g., ETH)")
    close_parser.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    close_parser.add_argument("--sub-wallet", action="store_true", help="Close on sub-wallet")
    
    # Price command
    price_parser = subparsers.add_parser("price", help="Get current price")
    price_parser.add_argument("symbol", help="Symbol to check (e.g., ETH)")
    
    # Switch command
    switch_parser = subparsers.add_parser("switch", help="Switch between wallets")
    switch_parser.add_argument("wallet", choices=["main", "sub"], help="Wallet to switch to")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    # Show help if no command
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Create CLI instance
    cli = TradingCLI()
    
    # Execute command
    if args.command == "status":
        cli.cmd_status(args)
    elif args.command == "trade":
        cli.cmd_trade(args)
    elif args.command == "close":
        cli.cmd_close(args)
    elif args.command == "price":
        cli.cmd_price(args)
    elif args.command == "switch":
        cli.cmd_switch(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)