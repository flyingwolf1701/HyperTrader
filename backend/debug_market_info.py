#!/usr/bin/env python3
"""
Debug script to check market info structure
"""

import sys
import os
import json
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from exchange.hyperliquid_sdk import HyperliquidClient


def main():
    """Check the structure of market info"""
    logger.info("Checking market info structure...")
    
    try:
        client = HyperliquidClient(use_testnet=True, use_sub_wallet=False)
        
        # Get market info for ETH
        market_info = client.get_market_info("ETH")
        
        # Print all keys
        logger.info(f"\nMarket info keys for ETH:")
        for key in market_info.keys():
            logger.info(f"  - {key}: {market_info[key]}")
        
        # Pretty print full structure
        logger.info(f"\nFull market info structure:")
        print(json.dumps(market_info, indent=2))
        
    except Exception as e:
        logger.error(f"Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()