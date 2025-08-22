import asyncio
import ccxt.async_support as ccxt
from decimal import Decimal
import os
from dotenv import load_dotenv

async def test_hyperliquid_connection():
    """Test direct connection to HyperLiquid testnet"""
    
    # Load environment variables from .env
    load_dotenv('.env')
    api_key = os.getenv('HYPERLIQUID_API_KEY')
    private_key = os.getenv('HYPERLIQUID_SECRET_KEY')
    
    if not api_key or not private_key:
        print("ERROR: Missing API credentials in .env file")
        return None, None
    
    # Mask keys for display
    masked_api = f"{api_key[:6]}...{api_key[-4:]}" if api_key else "None"
    print(f"Using API key: {masked_api}")
    
    try:
        print("Connecting to HyperLiquid testnet...")
        
        # Create exchange instance
        exchange = ccxt.hyperliquid({
            'apiKey': api_key,
            'privateKey': private_key,
            'sandbox': True,  # Use testnet
            'options': {
                'defaultType': 'swap',
            },
        })
        
        # Load markets
        print("Loading markets...")
        markets = await exchange.load_markets()
        print(f"Loaded {len(markets)} markets")
        
        # Find BTC market
        btc_markets = [symbol for symbol in markets.keys() if 'BTC' in symbol and 'USDC' in symbol]
        print(f"BTC markets: {btc_markets[:5]}")
        
        if btc_markets:
            btc_symbol = btc_markets[0]
            print(f"Testing price fetch for {btc_symbol}")
            
            # Get ticker
            ticker = await exchange.fetch_ticker(btc_symbol)
            print(f"Ticker data: {ticker}")
            price = ticker.get('last') or ticker.get('mark') or ticker.get('close') or ticker.get('bid')
            print(f"Current price: ${price}")
            
            # Get balance
            print("Checking balance...")
            balance = await exchange.fetch_balance()
            usdc_balance = balance.get('USDC', {}).get('total', 0)
            print(f"USDC Balance: ${usdc_balance}")
            
            print("HyperLiquid connection successful!")
            return btc_symbol, ticker['last']
        else:
            print("No BTC/USDC markets found")
            return None, None
            
    except Exception as e:
        print(f"Connection failed: {e}")
        return None, None
    finally:
        if 'exchange' in locals():
            await exchange.close()

if __name__ == "__main__":
    asyncio.run(test_hyperliquid_connection())