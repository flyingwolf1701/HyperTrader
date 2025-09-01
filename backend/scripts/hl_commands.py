#!/usr/bin/env python3
"""
Hyperliquid SDK Commands - Direct implementation using the official SDK
"""

import argparse
import sys
from decimal import Decimal
from typing import Optional
from loguru import logger

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Import settings
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import settings


def get_client(use_sub_wallet=False):
    """Initialize Hyperliquid SDK clients"""
    # Use testnet URL - don't append /info, SDK does that
    base_url = "https://api.hyperliquid-testnet.xyz"
    
    # Get credentials from settings
    private_key = settings.HYPERLIQUID_TESTNET_PRIVATE_KEY
    wallet_address = settings.hyperliquid_wallet_key
    
    # Create wallet object from private key
    from eth_account import Account
    wallet = Account.from_key(private_key)
    
    # Initialize Info client (for read operations)
    info = Info(base_url, skip_ws=True)
    
    # Initialize Exchange client
    if use_sub_wallet:
        # Use the sub-wallet for trading
        sub_wallet_address = settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG
        exchange = Exchange(
            wallet=wallet,
            base_url=base_url,
            vault_address=sub_wallet_address  # Trade on behalf of sub-wallet
        )
        logger.info(f"Using sub-wallet {sub_wallet_address[:8]}... via agent {wallet.address[:8]}...")
        # Return info configured for sub-wallet
        return info, exchange, sub_wallet_address
    elif wallet.address.lower() != wallet_address.lower():
        # API key trading for main wallet
        exchange = Exchange(
            wallet=wallet,
            base_url=base_url
        )
        logger.info(f"Using API agent {wallet.address[:8]}... for main wallet {wallet_address[:8]}...")
        return info, exchange, wallet_address
    else:
        # Direct wallet trading
        exchange = Exchange(
            wallet=wallet,
            base_url=base_url
        )
        logger.info(f"Using direct wallet {wallet_address[:8]}...")
        return info, exchange, wallet_address


def cmd_status(sub_wallet=False):
    """Display account status"""
    try:
        info, exchange, wallet_to_check = get_client(sub_wallet)
        
        logger.info("=" * 60)
        logger.info("ACCOUNT STATUS")
        logger.info("=" * 60)
        
        # Get account state for the correct wallet
        user_state = info.user_state(wallet_to_check)
        
        # Extract balance info
        margin_summary = user_state.get("marginSummary", {})
        account_value = float(margin_summary.get("accountValue", 0))
        total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
        
        logger.info("Account Balance:")
        logger.info(f"  Total Value: ${account_value:.2f}")
        logger.info(f"  Margin Used: ${total_margin_used:.2f}")
        logger.info(f"  Available: ${account_value - total_margin_used:.2f}")
        
        # Get positions
        positions = user_state.get("assetPositions", [])
        
        logger.info("\nPositions:")
        has_positions = False
        for pos_data in positions:
            position = pos_data.get("position", {})
            szi = float(position.get("szi", 0))
            
            if szi != 0:
                has_positions = True
                coin = position.get("coin")
                entry_px = float(position.get("entryPx", 0))
                unrealized_pnl = float(pos_data.get("unrealizedPnl", 0))
                side = "LONG" if szi > 0 else "SHORT"
                
                logger.info(f"  {coin}: {side}")
                logger.info(f"    Size: {abs(szi):.6f} {coin}")
                logger.info(f"    Entry: ${entry_px:.2f}")
                logger.info(f"    Unrealized PnL: ${unrealized_pnl:.2f}")
        
        if not has_positions:
            logger.info("  No open positions")
            
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        sys.exit(1)


def cmd_trade(symbol: str, amount: float, leverage: int = 10, short: bool = False, sub_wallet: bool = False):
    """Open a trade position"""
    try:
        info, exchange, _ = get_client(sub_wallet)
        
        logger.info("=" * 60)
        logger.info(f"OPENING {'SHORT' if short else 'LONG'} TRADE")
        logger.info("=" * 60)
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Position Size: ${amount}")
        logger.info(f"Leverage: {leverage}x")
        logger.info(f"Direction: {'SHORT' if short else 'LONG'}")
        logger.info("=" * 60)
        
        # Get current price
        all_mids = info.all_mids()
        current_price = float(all_mids.get(symbol, 0))
        
        if current_price == 0:
            logger.error(f"Could not get price for {symbol}")
            sys.exit(1)
            
        logger.info(f"Current Price: ${current_price:.2f}")
        
        # Calculate position size in base currency
        # Round to 4 decimal places (ETH has szDecimals=4)
        position_size = round(amount / current_price, 4)
        
        # Set leverage
        logger.info(f"Setting leverage to {leverage}x...")
        try:
            leverage_result = exchange.update_leverage(
                leverage=leverage,
                name=symbol,
                is_cross=True
            )
            if leverage_result.get("status") == "ok":
                logger.info("Leverage set successfully")
            else:
                logger.warning(f"Leverage setting failed: {leverage_result}")
        except Exception as e:
            logger.warning(f"Failed to set leverage: {e}")
        
        # Place market order
        position_type = "SHORT" if short else "LONG"
        logger.info(f"Opening {position_type} position for {position_size:.6f} {symbol}...")
        
        order_result = exchange.market_open(
            name=symbol,
            is_buy=not short,  # Buy for long, sell for short
            sz=position_size,
            px=None,  # Let the SDK calculate the price
            slippage=0.01  # 1% slippage tolerance
        )
        
        logger.info(f"Order result: {order_result}")
        
        if order_result.get("status") == "ok":
            logger.success("=" * 60)
            logger.success("TRADE OPENED SUCCESSFULLY")
            
            # Get order details - note the response structure is nested
            response = order_result.get("response", {})
            data = response.get("data", {})
            statuses = data.get("statuses", [])
            
            if statuses:
                status = statuses[0]
                if "filled" in status:
                    filled = status["filled"]
                    logger.success(f"Order ID: {filled.get('oid')}")
                    logger.success(f"Filled Size: {filled.get('totalSz')} {symbol}")
                    logger.success(f"Average Price: ${filled.get('avgPx')}")
                elif "resting" in status:
                    resting = status["resting"]
                    logger.info(f"Order ID: {resting.get('oid')}")
                    logger.info(f"Order is resting (limit order)")
                elif "error" in status:
                    logger.error(f"Order error: {status['error']}")
                    sys.exit(1)
                else:
                    logger.warning(f"Unknown order status: {status}")
            else:
                logger.warning("No status information in order result")
            
            logger.success("=" * 60)
        else:
            logger.error(f"Trade failed: {order_result}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to open trade: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_close(symbol: str, sub_wallet: bool = False):
    """Close position for a symbol"""
    try:
        info, exchange, wallet_to_check = get_client(sub_wallet)
        
        logger.info("=" * 60)
        logger.info("CLOSING POSITION")
        logger.info("=" * 60)
        
        # Get current position for the correct wallet
        user_state = info.user_state(wallet_to_check)
        
        positions = user_state.get("assetPositions", [])
        position_to_close = None
        
        for pos_data in positions:
            position = pos_data.get("position", {})
            if position.get("coin") == symbol:
                szi = float(position.get("szi", 0))
                if szi != 0:
                    position_to_close = {
                        "size": abs(szi),
                        "is_long": szi > 0,
                        "coin": symbol
                    }
                    break
        
        if not position_to_close:
            logger.info(f"No position to close for {symbol}")
            return
        
        # Close the position
        is_buy = not position_to_close["is_long"]  # Buy to close short, sell to close long
        
        logger.info(f"Closing {'LONG' if position_to_close['is_long'] else 'SHORT'} position")
        logger.info(f"Size: {position_to_close['size']:.6f} {symbol}")
        
        # Use market_open with opposite side to close (market_close seems unreliable)
        is_buy_to_close = not position_to_close["is_long"]  # Sell to close long, buy to close short
        
        logger.info(f"Placing {'sell' if not is_buy_to_close else 'buy'} order to close position...")
        
        result = exchange.market_open(
            name=symbol,
            is_buy=is_buy_to_close,
            sz=position_to_close["size"],
            px=None,
            slippage=0.01
        )
        
        logger.info(f"Close result: {result}")
        
        if result and result.get("status") == "ok":
            logger.success("Position closed successfully")
            # Parse the response
            response = result.get("response", {})
            data = response.get("data", {})
            statuses = data.get("statuses", [])
            if statuses and "filled" in statuses[0]:
                filled = statuses[0]["filled"]
                logger.success(f"Closed at average price: ${filled.get('avgPx')}")
        else:
            logger.error(f"Failed to close position: {result}")
            
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