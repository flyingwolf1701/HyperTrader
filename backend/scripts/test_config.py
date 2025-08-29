#!/usr/bin/env python3
"""
Test sub-wallet configuration
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from src.utils.config import settings, get_long_subwallet_credentials
    
    print("Configuration Test:")
    print(f"  hyperliquid_testnet: {settings.hyperliquid_testnet}")
    print(f"  HYPERLIQUID_TESTNET_SUB_WALLET_LONG: {'SET' if settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG else 'NOT SET'}")
    print(f"  HYPERLIQUID_TESTNET_SUB_WALLET_LONG_private: {'SET' if settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG_private else 'NOT SET'}")
    
    wallet_key, private_key = get_long_subwallet_credentials(testnet=True)
    print(f"\nCredentials Retrieved:")
    print(f"  Using wallet key: {'SUBWALLET' if wallet_key == settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG else 'MAIN WALLET'}")
    print(f"  Wallet key length: {len(wallet_key) if wallet_key else 0}")
    print(f"  Private key length: {len(private_key) if private_key else 0}")
    
except Exception as e:
    print(f"Configuration error: {e}")
