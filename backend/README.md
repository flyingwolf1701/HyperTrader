# HyperTrader Backend v6.0.0

Multi-position crypto trading bot implementing the 4-phase position fragment strategy on HyperLiquid DEX testnet.

## Features

✅ **Multi-Position Management** - Run multiple trading positions simultaneously  
✅ **Position Fragment Logic** - 10% fragments calculated at peak, 25% hedge at valley  
✅ **4-Phase Strategy** - ADVANCE → RETRACEMENT → DECLINE → RECOVERY → RESET  
✅ **File-Based State** - No database required, each position in `strategies/` directory  
✅ **WebSocket Support** - Real-time price monitoring (single symbol currently)

## Quick Start

### Prerequisites
- Python 3.13+
- HyperLiquid testnet account with funds
- `uv` package manager

### Installation

```bash
cd backend
uv sync
```

### Configuration

Create `.env` file:
```env
HYPERLIQUID_WALLET_KEY=0x329C49392608175A071fC9AF982fF625f119fFAE 
HYPERLIQUID_PRIVATE_KEY=...
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz
```

### Run Server

```bash
uv run uvicorn app.main:app --reload
```

API available at `http://localhost:8000`, docs at `http://localhost:8000/docs`

## Trading Operations

### Start Multiple Positions

```bash
# Start ETH position
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETH/USDC:USDC",
    "position_size_usd": 5000.0,
    "unit_size": 0.10,
    "leverage": 25
  }'

# Start PURR position (runs alongside ETH)
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PURR/USDC:USDC",
    "position_size_usd": 100.0,
    "unit_size": 0.005,
    "leverage": 10
  }'
```

### Update Positions

```bash
# Update all positions
curl -X POST "http://localhost:8000/api/v1/strategy/update-all"

# Update specific position (URL encode symbol)
curl -X POST "http://localhost:8000/api/v1/strategy/update/ETH%2FUSDC%3AUSDC"
```

### Monitor Status

```bash
# View all active strategies
curl "http://localhost:8000/api/v1/strategies"

# Check specific strategy
curl "http://localhost:8000/api/v1/strategy/ETH%2FUSDC%3AUSDC/status"

# View exchange positions (with size and mark_price)
curl "http://localhost:8000/api/v1/positions"

# View balances
curl "http://localhost:8000/api/v1/balances"
```

### Stop Positions

```bash
# Stop specific position
curl -X POST "http://localhost:8000/api/v1/strategy/stop/ETH%2FUSDC%3AUSDC"
```

## WebSocket Monitoring

```bash
# Start WebSocket monitoring (currently single symbol)
curl -X POST "http://localhost:8000/api/v1/strategy/start-monitoring"

# Stop monitoring
curl -X POST "http://localhost:8000/api/v1/strategy/stop-monitoring"
```

## Manual Trading

```bash
# Place market order
curl -X POST "http://localhost:8000/api/v1/order" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETH/USDC:USDC",
    "side": "buy",
    "amount": 0.1,
    "type": "market"
  }'
```

## Testing

### Run Strategy Tests

```bash
# Test all 4 phases with simulated prices
uv run python test_v6_strategy.py

# Test multi-position updates
uv run python test_multi_update.py

# Monitor strategy states
watch -n 1 'for f in strategies/*.json; do echo "=== $f ==="; cat "$f" | python -m json.tool | head -15; done'
```

## Strategy Phases

**ADVANCE**: Track peaks, calculate position_fragment (10% of position value)  
**RETRACEMENT**: Scale out using position_fragment per unit decline  
**DECLINE**: Hold shorts, calculate hedge_fragment at valley +1 (25% of short value)  
**RECOVERY**: Scale back in using hedge_fragment per unit rise  
**RESET**: Return to ADVANCE when fully long

## State Files

```bash
strategies/
├── strategy_ETH_USDC_USDC.json    # ETH position state
├── strategy_PURR_USDC_USDC.json   # PURR position state
└── strategy_BTC_USDC_USDC.json    # BTC position state
```

## Troubleshooting

**Position data shows 0.0 for size/mark_price**
- Fixed: Now correctly reads HyperLiquid's `contracts` field and calculates mark_price

**Can't run multiple positions**
- Fixed: Multi-position support added with separate state files

**Updates not working for all positions**
- Fixed: Use `/strategy/update-all` or update individually

**WebSocket only monitors one symbol**
- Known limitation: WebSocket currently supports single symbol monitoring

## Recent Updates (August 25, 2025)

- ✅ Fixed update mechanism for multiple positions
- ✅ Added parallel position updates
- ✅ Fixed position data (size and mark_price now correct)
- ✅ Separate state files per position
- ✅ URL path parameter support for symbols with colons

## Next Steps

1. Update WebSocket to monitor multiple symbols
2. Add batch stop operations for all positions
3. Test RESET mechanism with multiple positions
4. Add position performance tracking

---

**⚠️ Testnet Only** - No real money at risk. Test thoroughly before mainnet deployment.