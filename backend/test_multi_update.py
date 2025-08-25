#!/usr/bin/env python3
"""Test multi-position update functionality"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_multi_position_updates():
    """Test that update-all endpoint updates all active positions"""
    
    print("\n=== Testing Multi-Position Updates ===\n")
    
    # 1. Check current active positions
    print("1. Checking current active positions...")
    response = requests.get(f"{BASE_URL}/strategies")
    if response.status_code == 200:
        data = response.json()
        print(f"   Found {data['count']} active positions")
        for symbol, state in data.get('strategies', {}).items():
            print(f"   - {symbol}: Phase={state['phase']}, Unit={state['current_unit']}")
    else:
        print(f"   Error: {response.status_code}")
        return
    
    # 2. Test update-all endpoint
    print("\n2. Testing update-all endpoint...")
    response = requests.post(f"{BASE_URL}/strategy/update-all")
    if response.status_code == 200:
        results = response.json()
        print(f"   Successfully updated {len(results.get('results', []))} positions")
        for result in results.get('results', []):
            if result.get('success'):
                print(f"   - {result.get('symbol')}: {result.get('message', 'Updated')}")
                if 'unit_change' in result:
                    print(f"     Unit change: {result['unit_change']}")
            else:
                print(f"   - {result.get('symbol')}: ERROR - {result.get('error')}")
    else:
        print(f"   Error: {response.status_code}")
        print(f"   Response: {response.text}")
    
    # 3. Test individual position updates
    print("\n3. Testing individual position updates...")
    response = requests.get(f"{BASE_URL}/strategies")
    if response.status_code == 200:
        data = response.json()
        for symbol in list(data.get('strategies', {}).keys())[:2]:  # Test first 2
            print(f"\n   Updating {symbol}...")
            # URL encode the symbol
            import urllib.parse
            encoded_symbol = urllib.parse.quote(symbol)
            
            response = requests.post(f"{BASE_URL}/strategy/update/{encoded_symbol}")
            if response.status_code == 200:
                result = response.json()
                print(f"   Success: {result.get('message', 'Updated')}")
                if 'unit_change' in result:
                    print(f"   Unit change: {result['unit_change']}")
                if 'phase' in result:
                    print(f"   Current phase: {result['phase']}")
            else:
                print(f"   Error: {response.status_code}")
                print(f"   Response: {response.text}")
    
    # 4. Test legacy update endpoint (should update all)
    print("\n4. Testing legacy update endpoint...")
    response = requests.post(f"{BASE_URL}/strategy/update")
    if response.status_code == 200:
        result = response.json()
        if 'results' in result:
            print(f"   Updated all positions ({len(result['results'])} total)")
        else:
            print(f"   Updated single position")
            print(f"   Result: {json.dumps(result, indent=2)}")
    else:
        print(f"   Error: {response.status_code}")
    
    print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    try:
        test_multi_position_updates()
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to server. Make sure the backend is running.")
    except Exception as e:
        print(f"Error: {e}")