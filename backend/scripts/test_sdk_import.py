#!/usr/bin/env python3
"""
Simple test to verify SDK import works
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from src.exchange.hyperliquid_sdk import HyperliquidSDK
    print("[OK] HyperliquidSDK import successful!")
    
    # Test basic instantiation (without real credentials)
    try:
        sdk = HyperliquidSDK(
            api_key="test_key",
            api_secret="0x" + "0" * 64,  # Dummy 64-char hex string
            base_url="https://api.hyperliquid-testnet.xyz"
        )
        print("[OK] SDK instantiation successful!")
        print(f"   Wallet address: {sdk.wallet_address}")
    except Exception as e:
        print(f"[WARN] SDK instantiation failed: {e}")
        
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
