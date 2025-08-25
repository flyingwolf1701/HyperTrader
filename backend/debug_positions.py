#!/usr/bin/env python3
"""Debug raw position data from CCXT"""

import asyncio
import json
from app.services.exchange import ExchangeManager

async def main():
    exchange = ExchangeManager()
    await exchange.initialize()
    
    # Get raw positions directly from CCXT
    raw = await exchange.exchange.fetch_positions()
    
    print("Raw position data from CCXT:")
    print(json.dumps(raw, indent=2, default=str))
    
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
