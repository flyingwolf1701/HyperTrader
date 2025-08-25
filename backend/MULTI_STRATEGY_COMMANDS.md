# Multi-Strategy Support - Command Reference

## ✅ Multi-Strategy Support is NOW ACTIVE!

You can now run multiple trading strategies simultaneously on different symbols.

## API Commands

### 1. Start Multiple Strategies

Start ETH strategy:
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETH/USDC:USDC",
    "position_size_usd": 5000.0,
    "unit_size": 0.10,
    "leverage": 25
  }'
```

Start PURR strategy (runs alongside ETH):
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PURR/USDC:USDC",
    "position_size_usd": 100.0,
    "unit_size": 0.005,
    "leverage": 10
  }'
```

Start BTC strategy:
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDC:USDC",
    "position_size_usd": 1000.0,
    "unit_size": 50.0,
    "leverage": 20
  }'
```

### 2. View All Active Strategies

```bash
curl "http://localhost:8000/api/v1/strategies" | python -m json.tool
```

Returns:
```json
{
  "success": true,
  "count": 2,
  "strategies": {
    "ETH/USDC:USDC": { ... },
    "PURR/USDC:USDC": { ... }
  }
}
```

### 3. Check Specific Strategy Status

For ETH:
```bash
curl "http://localhost:8000/api/v1/strategy/ETH%2FUSDC%3AUSDC/status" | python -m json.tool
```

For PURR:
```bash
curl "http://localhost:8000/api/v1/strategy/PURR%2FUSDC%3AUSDC/status" | python -m json.tool
```

### 4. Stop Specific Strategy

Stop ETH only:
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/stop/ETH%2FUSDC%3AUSDC"
```

Stop PURR only:
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/stop/PURR%2FUSDC%3AUSDC"
```

### 5. Update Specific Strategy

*Note: Update endpoint needs to be enhanced to support specific symbols*

Currently updates all strategies:
```bash
curl -X POST "http://localhost:8000/api/v1/strategy/update"
```

## File Structure

Each strategy has its own state file:
```
backend/
├── strategies/
│   ├── strategy_ETH_USDC_USDC.json
│   ├── strategy_PURR_USDC_USDC.json
│   └── strategy_BTC_USDC_USDC.json
```

## Current Active Strategies

As of now, you have 2 strategies running:
1. **ETH/USDC:USDC** - $5000 position, 0.10 unit size
2. **PURR/USDC:USDC** - $100 position, 0.005 unit size

## Monitor All Strategies

Create a monitoring script:
```python
#!/usr/bin/env python3
import json
import time
import requests

while True:
    response = requests.get("http://localhost:8000/api/v1/strategies")
    strategies = response.json()["strategies"]
    
    print(f"\n{'='*60}")
    print(f"Active Strategies: {len(strategies)}")
    print(f"{'='*60}")
    
    for symbol, state in strategies.items():
        print(f"\n{symbol}:")
        print(f"  Phase: {state['phase']}")
        print(f"  Unit: {state['current_unit']} (Peak: {state['peak_unit']})")
        print(f"  Long: ${state['current_long_position']:.2f}")
        print(f"  Short: ${state['current_short_position']:.2f}")
    
    time.sleep(5)
```

## Limitations to Fix Later

1. **WebSocket monitoring** - Currently only monitors one symbol at a time
2. **Update endpoint** - Needs to support updating specific strategies
3. **Batch operations** - No way to stop all strategies at once

## Benefits

✅ **Run multiple strategies** - Trade ETH, BTC, PURR simultaneously
✅ **Independent tracking** - Each strategy has its own state file
✅ **No conflicts** - Strategies don't interfere with each other
✅ **Easy management** - Check status of each individually

Your trading bot now supports true multi-strategy operation!