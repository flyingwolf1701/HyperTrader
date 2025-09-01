"""
Basic Trading Commands Script
Direct trading operations using native Hyperliquid client
Bypasses strategy manager for simple manual trading
"""
import asyncio
import sys
import argparse
from pathlib import Path
from decimal import Decimal
from typing import Optional
from loguru import logger

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.exchange.exchange_client import HyperliquidExchangeClient


class BasicTrader:
    """Simple trading interface using direct exchange client"""
    
    def __init__(self, testnet: bool = True, use_vault: bool = False):
        """Initialize with exchange client"""
        self.testnet = testnet
        self.use_vault = use_vault
        self.client = HyperliquidExchangeClient(testnet=testnet, use_vault=use_vault)
        
        # Configure logging
        logger.remove()
        logger.add(
            sys.stdout,
            colorize=True,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>",
            level="INFO"
        )
    
    def _format_symbol(self, symbol: str) -> str:
        """Convert simple symbol (ETH) to full format (ETH/USDC:USDC)"""
        if "/" not in symbol:
            return f"{symbol}/USDC:USDC"
        return symbol
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current price from exchange API"""
        return self.client.get_current_price(symbol)
    
    async def open_trade(
        self,
        symbol: str,
        position_size: Decimal,
        unit_size: Optional[Decimal] = None,
        leverage: int = 25,
        order_type: str = "market",
        limit_price: Optional[Decimal] = None
    ):
        """Open a long position"""
        formatted_symbol = self._format_symbol(symbol)
        base_symbol = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info("=" * 60)
        logger.info("OPENING TRADE")
        logger.info("=" * 60)
        logger.info(f"Symbol: {formatted_symbol}")
        logger.info(f"Position Size: ${position_size}")
        if unit_size:
            logger.info(f"Unit Size: ${unit_size}")
        logger.info(f"Leverage: {leverage}x")
        logger.info(f"Order Type: {order_type.upper()}")
        if limit_price:
            logger.info(f"Limit Price: ${limit_price}")
        logger.info("=" * 60)
        
        try:
            # Get current price from exchange
            current_price = await self._get_current_price(formatted_symbol)
            logger.info(f"Current Market Price: ${current_price:.2f}")
            
            # Check current balance
            balance = self.client.get_balance("USDC")
            logger.info(f"Available Balance: ${balance.available:.2f}")
            
            # Check for existing position
            existing_position = self.client.get_position(formatted_symbol)
            if existing_position:
                logger.warning(f"Existing position found: {existing_position.side} {existing_position.size}")
                response = input("Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Trade cancelled")
                    return
            
            # Set leverage (optional - skip if it fails)
            if leverage:
                logger.info(f"Setting leverage to {leverage}x...")
                leverage_set = self.client.set_leverage(formatted_symbol, leverage)
                if not leverage_set:
                    logger.warning("Failed to set leverage, continuing with default")
                    # Don't return - continue with trade
            
            # Calculate coin amount
            coin_amount = position_size / current_price
            
            # Determine order price
            if order_type.lower() == "limit":
                if not limit_price:
                    logger.error("Limit price required for limit orders")
                    return
                order_price = limit_price
                logger.info(f"Placing LIMIT order at ${order_price}")
            else:
                # Market order - use current price with slippage buffer
                slippage_buffer = current_price * Decimal("0.01")  # 1% slippage
                order_price = current_price + slippage_buffer
                logger.info(f"Placing MARKET order (price with slippage: ${order_price:.2f})")
            
            # Place order
            logger.info(f"Opening long position for {coin_amount:.6f} {base_symbol}...")
            
            result = self.client.place_order(
                symbol=formatted_symbol,
                side="buy",
                size=coin_amount,
                order_type=order_type.lower(),
                price=order_price,
                reduce_only=False
            )
            
            if result.status == "filled":
                logger.success(f"✅ Trade executed successfully!")
                logger.info(f"Order ID: {result.id}")
                logger.info(f"Filled at: ${result.price}")
                logger.info(f"Coin Amount: {coin_amount:.6f}")
                margin_used = position_size / Decimal(leverage) if leverage else position_size
                logger.info(f"Margin Used: ${margin_used:.2f}")
                
                # Get updated position
                await asyncio.sleep(0.5)  # Brief wait for position update
                position = self.client.get_position(formatted_symbol)
                if position:
                    logger.info("\nPosition Details:")
                    logger.info(f"  Side: {position.side}")
                    logger.info(f"  Size: {position.size:.6f}")
                    logger.info(f"  Entry Price: ${position.entry_price:.2f}")
                    logger.info(f"  Mark Price: ${position.mark_price:.2f}")
                    logger.info(f"  Unrealized PnL: ${position.unrealized_pnl:.2f}")
            elif result.status == "open":
                logger.info(f"⏳ Limit order placed successfully!")
                logger.info(f"Order ID: {result.id}")
                logger.info(f"Order will fill when price reaches ${order_price}")
            else:
                logger.error(f"Trade failed: {result.status}")
                if result.info:
                    logger.error(f"Details: {result.info}")
            
        except Exception as e:
            logger.error(f"Error opening trade: {e}")
    
    async def close_trade(self, symbol: str, order_type: str = "market", limit_price: Optional[Decimal] = None):
        """Close an existing position"""
        formatted_symbol = self._format_symbol(symbol)
        base_symbol = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info("=" * 60)
        logger.info("CLOSING POSITION")
        logger.info("=" * 60)
        
        try:
            # Get current position
            position = self.client.get_position(formatted_symbol)
            
            if not position:
                logger.warning(f"No position found for {formatted_symbol}")
                return
            
            # Get current price from exchange
            current_price = await self._get_current_price(formatted_symbol)
            
            logger.info(f"Current Position:")
            logger.info(f"  Symbol: {formatted_symbol}")
            logger.info(f"  Side: {position.side}")
            logger.info(f"  Size: {position.size:.6f}")
            logger.info(f"  Entry Price: ${position.entry_price:.2f}")
            logger.info(f"  Current Price: ${current_price:.2f}")
            logger.info(f"  Unrealized PnL: ${position.unrealized_pnl:.2f}")
            
            # Confirm closure
            response = input("\nClose this position? (y/n): ")
            if response.lower() != 'y':
                logger.info("Closure cancelled")
                return
            
            # Determine order side and price
            close_side = "sell" if position.side == "long" else "buy"
            
            if order_type.lower() == "limit":
                if not limit_price:
                    logger.error("Limit price required for limit orders")
                    return
                order_price = limit_price
                logger.info(f"Placing LIMIT close order at ${order_price}")
            else:
                # Market order - use current price with slippage buffer
                slippage_buffer = current_price * Decimal("0.01")  # 1% slippage
                if close_side == "sell":
                    order_price = current_price - slippage_buffer
                else:
                    order_price = current_price + slippage_buffer
                logger.info(f"Placing MARKET close order (price with slippage: ${order_price:.2f})")
            
            # Close position
            logger.info("Closing position...")
            
            result = self.client.place_order(
                symbol=formatted_symbol,
                side=close_side,
                size=position.size,
                order_type=order_type.lower(),
                price=order_price,
                reduce_only=True
            )
            
            if result.status == "filled":
                logger.success(f"✅ Position closed successfully!")
                logger.info(f"Order ID: {result.id}")
                logger.info(f"Filled at: ${result.price}")
                
                # Calculate realized PnL
                if position.side == "long":
                    realized_pnl = (result.price - position.entry_price) * position.size
                else:
                    realized_pnl = (position.entry_price - result.price) * position.size
                
                pnl_icon = "📈" if realized_pnl > 0 else "📉"
                logger.info(f"{pnl_icon} Realized PnL: ${realized_pnl:.2f}")
            elif result.status == "open":
                logger.info(f"⏳ Limit close order placed successfully!")
                logger.info(f"Order ID: {result.id}")
                logger.info(f"Order will fill when price reaches ${order_price}")
            else:
                logger.error(f"Failed to close position: {result.status}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def check_status(self, symbol: Optional[str] = None):
        """Check account and position status"""
        logger.info("=" * 60)
        logger.info("ACCOUNT STATUS")
        logger.info("=" * 60)
        
        try:
            # Get balance
            balance = self.client.get_balance("USDC")
            logger.info(f"Account Balance:")
            logger.info(f"  Available: ${balance.available:.2f}")
            logger.info(f"  Total: ${balance.total:.2f}")
            logger.info(f"  Used: ${balance.used:.2f}")
            
            # Check specific position or all positions
            if symbol:
                formatted_symbol = self._format_symbol(symbol)
                current_price = await self._get_current_price(formatted_symbol)
                
                position = self.client.get_position(formatted_symbol)
                
                if position:
                    logger.info(f"\nPosition for {formatted_symbol}:")
                    logger.info(f"  Side: {position.side}")
                    logger.info(f"  Size: {position.size:.6f}")
                    logger.info(f"  Entry Price: ${position.entry_price:.2f}")
                    logger.info(f"  Current Price: ${current_price:.2f}")
                    logger.info(f"  Mark Price: ${position.mark_price:.2f}")
                    logger.info(f"  Unrealized PnL: ${position.unrealized_pnl:.2f}")
                    logger.info(f"  Margin Used: ${position.margin_used:.2f}")
                    
                    # Calculate percentage gain/loss
                    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    if position.side == "short":
                        pnl_pct = -pnl_pct
                    logger.info(f"  PnL %: {pnl_pct:.2f}%")
                else:
                    logger.info(f"\nNo position for {formatted_symbol}")
            else:
                # Check common symbols
                logger.info("\nChecking positions...")
                symbols_to_check = ["ETH", "BTC", "SOL", "ARB", "AVAX"]
                has_positions = False
                
                for sym in symbols_to_check:
                    formatted_sym = self._format_symbol(sym)
                    position = self.client.get_position(formatted_sym)
                    
                    if position:
                        has_positions = True
                        pnl_icon = "📈" if position.unrealized_pnl > 0 else "📉"
                        logger.info(f"\n{sym}:")
                        logger.info(f"  {position.side.upper()} {position.size:.6f}")
                        logger.info(f"  Entry: ${position.entry_price:.2f}")
                        logger.info(f"  Current: ${position.mark_price:.2f}")
                        logger.info(f"  {pnl_icon} PnL: ${position.unrealized_pnl:.2f}")
                
                if not has_positions:
                    logger.info("No open positions found")
            
        except Exception as e:
            logger.error(f"Error checking status: {e}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Basic Trading Commands - Direct Hyperliquid Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Open a market order long position
  uv run python scripts/basic_commands.py trade ETH 2500 --unit-size 2.5 --leverage 25
  
  # Open a limit order long position
  uv run python scripts/basic_commands.py trade ETH 2500 --leverage 25 --order-type limit --limit-price 3800
  
  # Close a position with market order
  uv run python scripts/basic_commands.py close ETH
  
  # Close a position with limit order
  uv run python scripts/basic_commands.py close ETH --order-type limit --limit-price 3850
  
  # Check all positions
  uv run python scripts/basic_commands.py status
  
  # Check specific position
  uv run python scripts/basic_commands.py status ETH
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Trade command
    trade_parser = subparsers.add_parser("trade", help="Open a trading position")
    trade_parser.add_argument("symbol", help="Trading symbol (e.g., ETH, BTC)")
    trade_parser.add_argument("position_size", type=float, help="Position size in USD")
    trade_parser.add_argument("--unit-size", type=float, help="Unit size in USD (optional)")
    trade_parser.add_argument("--leverage", type=int, default=25, help="Leverage (default: 25)")
    trade_parser.add_argument("--order-type", choices=["market", "limit"], default="market", 
                            help="Order type (default: market)")
    trade_parser.add_argument("--limit-price", type=float, help="Limit price for limit orders")
    trade_parser.add_argument("--vault", action="store_true", help="Use sub-account/vault")
    trade_parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    
    # Close command
    close_parser = subparsers.add_parser("close", help="Close a position")
    close_parser.add_argument("symbol", help="Symbol to close (e.g., ETH, BTC)")
    close_parser.add_argument("--order-type", choices=["market", "limit"], default="market",
                            help="Order type (default: market)")
    close_parser.add_argument("--limit-price", type=float, help="Limit price for limit orders")
    close_parser.add_argument("--vault", action="store_true", help="Use sub-account/vault")
    close_parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check account and position status")
    status_parser.add_argument("symbol", nargs="?", help="Specific symbol to check (optional)")
    status_parser.add_argument("--vault", action="store_true", help="Use sub-account/vault")
    status_parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Safety check for mainnet
    testnet = True
    if hasattr(args, 'mainnet') and args.mainnet:
        logger.warning("=" * 60)
        logger.warning("WARNING: MAINNET MODE")
        logger.warning("This will trade with REAL funds!")
        logger.warning("=" * 60)
        response = input("Are you absolutely sure? Type 'YES' to continue: ")
        
        if response != "YES":
            logger.info("Mainnet trading cancelled")
            return
        testnet = False
    
    # Initialize trader with vault option if specified
    use_vault = hasattr(args, 'vault') and args.vault
    trader = BasicTrader(testnet=testnet, use_vault=use_vault)
    
    # Execute command
    try:
        if args.command == "trade":
            # Validate limit order parameters
            if args.order_type == "limit" and not args.limit_price:
                logger.error("Limit price required for limit orders (use --limit-price)")
                return
                
            await trader.open_trade(
                symbol=args.symbol,
                position_size=Decimal(str(args.position_size)),
                unit_size=Decimal(str(args.unit_size)) if args.unit_size else None,
                leverage=args.leverage,
                order_type=args.order_type,
                limit_price=Decimal(str(args.limit_price)) if args.limit_price else None
            )
        
        elif args.command == "close":
            # Validate limit order parameters
            if hasattr(args, 'order_type') and args.order_type == "limit" and not args.limit_price:
                logger.error("Limit price required for limit orders (use --limit-price)")
                return
                
            await trader.close_trade(
                args.symbol,
                order_type=args.order_type if hasattr(args, 'order_type') else "market",
                limit_price=Decimal(str(args.limit_price)) if hasattr(args, 'limit_price') and args.limit_price else None
            )
        
        elif args.command == "status":
            await trader.check_status(args.symbol)
    
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())