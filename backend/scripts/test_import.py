#!/usr/bin/env python3
"""Test SDK import"""

try:
    from src.exchange.hyperliquid_sdk import HyperliquidSDK
    print("[OK] SDK import successful")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
