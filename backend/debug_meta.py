#!/usr/bin/env python3
"""
Debug script to check full meta structure
"""

import sys
import os
import json
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hyperliquid.info import Info
from dotenv import load_dotenv

load_dotenv()


def main():
    """Check the full meta structure"""
    logger.info("Checking full meta structure...")
    
    try:
        # Use testnet
        info = Info("https://api.hyperliquid-testnet.xyz", skip_ws=True)
        
        # Get full meta
        meta = info.meta()
        
        # Check if we have universe key
        if "universe" in meta:
            logger.info(f"Found {len(meta['universe'])} assets in universe")
            
            # Find ETH
            for asset in meta["universe"]:
                if asset.get("name") == "ETH":
                    logger.info(f"\nETH asset info:")
                    print(json.dumps(asset, indent=2))
                    break
        else:
            logger.info("Keys in meta:")
            for key in meta.keys():
                logger.info(f"  - {key}")
            
            # Show first level structure
            logger.info("\nFull meta structure (truncated):")
            meta_str = json.dumps(meta, indent=2)
            print(meta_str[:2000])  # First 2000 chars
        
    except Exception as e:
        logger.error(f"Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()