#!/usr/bin/env python3

import asyncio
from app.services.exchange import exchange_manager
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_account():
    """Check account details and configuration"""
    try:
        logger.info("=" * 60)
        logger.info("CHECKING ACCOUNT CONFIGURATION")
        logger.info("=" * 60)
        
        # Show configuration
        logger.info(f"Wallet Address: {settings.HYPERLIQUID_WALLET_KEY}")
        logger.info(f"Testnet Mode: {settings.HYPERLIQUID_TESTNET}")
        logger.info(f"Private Key (first 10 chars): {settings.HYPERLIQUID_PRIVATE_KEY[:10]}...")
        
        # Initialize exchange
        await exchange_manager.initialize()
        logger.info("Exchange initialized successfully")
        
        # Check exchange configuration
        logger.info(f"Exchange options: {exchange_manager.exchange.options}")
        logger.info(f"Exchange sandbox mode: {exchange_manager.exchange.sandbox}")
        
        # Get balances with detailed logging
        logger.info("\nFetching balances...")
        params = {'user': settings.HYPERLIQUID_WALLET_KEY}
        
        # Try raw balance fetch to see what we get
        raw_balance = await exchange_manager.exchange.fetch_balance(params=params)
        logger.info(f"Raw balance response keys: {raw_balance.keys()}")
        logger.info(f"Total balances: {raw_balance.get('total', {})}")
        logger.info(f"Free balances: {raw_balance.get('free', {})}")
        logger.info(f"Used balances: {raw_balance.get('used', {})}")
        
        # Check if we're on testnet by looking at markets
        logger.info("\nChecking if we're on testnet...")
        if 'TEST' in [m.base for m in exchange_manager.markets.values()]:
            logger.info("✅ TEST token found - likely on testnet")
        else:
            logger.info("⚠️ No TEST token found - might be on mainnet")
            
        # Try to get account info directly
        logger.info("\nTrying to get account info...")
        try:
            account_info = await exchange_manager.exchange.fetch_status()
            logger.info(f"Exchange status: {account_info}")
        except Exception as e:
            logger.info(f"Could not fetch status: {e}")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await exchange_manager.close()

if __name__ == "__main__":
    asyncio.run(check_account())