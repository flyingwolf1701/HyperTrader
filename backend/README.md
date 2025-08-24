# HyperTrader Backend

Advanced crypto trading bot implementing a sophisticated 4-phase hedging strategy on HyperLiquid DEX. This system automatically manages long/hedge allocations based on price movements, providing downside protection while capturing upside gains.

**🎉 CURRENT STATUS: Fully Working Trading System!**

✅ **Order Placement**: Successfully tested on HyperLiquid testnet  
✅ **4-Phase Strategy**: Complete implementation with unit-based tracking  
✅ **Real-Time API**: Working endpoints for strategy management  
✅ **State Management**: File-based persistence (no database required)  

## =🚀 Quick Start

### Prerequisites

- Python 3.13+
- HyperLiquid testnet account with funds
- **No database required** - uses file-based state management

### Installation

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   ```

2. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn ccxt[asyncio] loguru pydantic
   ```

3. **Configure environment:**
   ```bash
   # Edit .env with your HyperLiquid testnet credentials
   ```

4. **Start the server:**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

The API will be available at `http://localhost:8000` with docs at `http://localhost:8000/docs`.

## =' Configuration

### Environment Variables (.env)

```env
# HyperLiquid API Configuration (Testnet)
HYPERLIQUID_WALLET_KEY=0xaabba699809309a8b5de2272c903f746f9976275
HYPERLIQUID_PRIVATE_KEY=0x110823f3cfe10b48cb55e2f20945b95846f8588ac6107574474e2484ef76ab4b
HYPERLIQUID_TESTNET=true
HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz

# Application Settings
ENVIRONMENT=development
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### HyperLiquid Testnet Setup

1. **Access HyperLiquid Testnet:**

   - Go to [HyperLiquid Testnet](https://app.hyperliquid-testnet.xyz)
   - Connect your wallet

2. **Get Test Funds:**

   - Use the testnet faucet to get test USDC
   - No real money required

3. **Generate API Credentials:**
   - Go to API section in testnet
   - Create an API wallet (for trading only, no withdrawal risk)
   - Copy the credentials to your `.env`

## 🧪 Testing the System

### 1. Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:

```
INFO:app.main:--- Starting HyperTrader Backend ---
INFO:app.services.exchange:ExchangeManager initialized with 50 markets.
INFO:app.main:Exchange manager initialized.
INFO:app.main:Simple API ready - query exchange directly for positions
INFO:     Application startup complete.
```

### 2. Test Basic API Endpoints

**Health Check:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","app":"HyperTrader"}
```

**Get Available Markets:**

```bash
curl http://localhost:8000/api/v1/markets
# Returns: {"pairs": ["PURR/USDC", "BTC/USDC", "TEST/USDC", ...]}
```

**Get Current Price:**

```bash
curl "http://localhost:8000/api/v1/price/BTC%2FUSDC%3AUSDC"
# Returns: {"symbol":"BTC/USDC:USDC","price":115986.0}
```

**Check Account Balances:**

```bash
curl http://localhost:8000/api/v1/balances
# Returns: {"success":true,"balances":{"USDC":1000.0}}
```

**Check Current Positions:**

```bash
curl http://localhost:8000/api/v1/positions
# Returns current positions on exchange
```

### 3. Test Manual Trading

**Place a Market Order:**

```bash
curl -X POST "http://localhost:8000/api/v1/order" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PURR/USDC:USDC",
    "side": "buy",
    "amount": 2,
    "type": "market"
  }'
# Returns: {"success":true,"order_id":"37965840433","filled":"None","status":"None"}
```

**Place a Limit Order:**

```bash
curl -X POST "http://localhost:8000/api/v1/order" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PURR/USDC:USDC",
    "side": "buy",
    "amount": 1,
    "type": "limit",
    "price": 5.0
  }'
```

### 4. Start the 4-Phase Trading Strategy

**Start a new strategy:**

```bash
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PURR/USDC:USDC",
    "position_size_usd": 50.0,
    "unit_size": 0.1,
    "leverage": 1
  }'
```

**Parameters:**
- `symbol`: Trading pair with futures format (e.g., "PURR/USDC:USDC", "BTC/USDC:USDC")
- `position_size_usd`: Total position size in USD (minimum $50 recommended)
- `unit_size`: Price movement per unit (e.g., 0.1 means each unit = $0.10 price move)
- `leverage`: Leverage multiplier (1 recommended for testing)

**Update Strategy (Check Price & Execute Trades):**

```bash
curl -X POST "http://localhost:8000/api/v1/strategy/update"
```

This checks current price against entry price, calculates unit movement, and executes trades according to the 4-phase logic.

**Check Strategy Status:**

```bash
curl "http://localhost:8000/api/v1/strategy/status"
# Returns comprehensive strategy state including:
# - Current phase (ADVANCE/RETRACEMENT/DECLINE/RECOVERY)
# - Unit positions and tracking
# - Position allocations (long_invested, long_cash, hedge_short)
# - Current vs entry price
```

**Stop Strategy:**

```bash
curl -X POST "http://localhost:8000/api/v1/strategy/stop"
# Removes strategy state file and stops automated trading
```

### 5. Monitor Trading Activity

**Check all open positions:**

```bash
curl "http://localhost:8000/api/v1/positions"
# Returns positions from the exchange directly
```

**View account balances:**

```bash
curl "http://localhost:8000/api/v1/balances"  
# Returns current USDC and other token balances
```

**Get current price for any symbol:**

```bash
curl "http://localhost:8000/api/v1/price/PURR%2FUSDC%3AUSDC"
# Returns real-time price data
```

## 📊 4-Phase Strategy Testing

### Understanding the Phases

**ADVANCE Phase:**
- Single unified long position tracking peaks
- Updates `peak_unit` on new highs
- Transitions to RETRACEMENT on first decline

**RETRACEMENT Phase:**
- Sells 12% of total portfolio per unit decline
- Converts long positions to cash progressively  
- Transitions to DECLINE when long positions exhausted

**DECLINE Phase:**
- Holds defensive cash positions
- Tracks valley formation (`valley_unit`)
- Transitions to RECOVERY on first uptick

**RECOVERY Phase:**
- Buys back 25% of available cash per unit up
- Systematic re-entry until fully invested
- System resets to ADVANCE when all cash deployed

### Test Scenarios

**Test 1: Complete Strategy Cycle**

```bash
# 1. Start with ETH (volatile testnet token)
curl -X POST "http://localhost:8000/api/v1/strategy/start" \
  -d '{"symbol": "ETH/USDC:USDC", "position_size_usd": 5000.0, "unit_size": 0.5, "leverage":25}'

# 2. Monitor current phase
curl "http://localhost:8000/api/v1/strategy/status"

# 3. Update strategy as price moves (run this repeatedly)
curl -X POST "http://localhost:8000/api/v1/strategy/update"

# 4. Watch for phase transitions and order placement
```

**Test 2: Manual Price Simulation**

Since testnet prices may not move much, you can test the logic by:
1. Starting strategy at current price
2. Adjusting `unit_size` to be very small (e.g., 0.01)
3. Natural price fluctuations will trigger unit changes
4. Monitor state transitions in real-time

**Expected Results:**
- ✅ ADVANCE → RETRACEMENT: First sell order at 12% of position
- ✅ Continued RETRACEMENT: Additional 12% sells on further declines  
- ✅ RETRACEMENT → DECLINE: When long position exhausted
- ✅ DECLINE → RECOVERY: First buy order at 25% of available cash
- ✅ RECOVERY → ADVANCE: System reset when fully re-invested

## 📊 Monitoring & Debugging

### File-Based State Management

The strategy state is saved to `strategy_state.json` in the backend directory:

```bash
# View current strategy state
cat strategy_state.json

# Monitor strategy file changes
watch -n 1 'cat strategy_state.json | python -m json.tool'
```

### Logging

The application uses Python's built-in logging. Key events to monitor:

**Important Log Messages:**
```
- "Unit change detected: X -> Y (Phase: Z)" - Strategy logic triggered
- "RETRACEMENT: Sold $X at unit Y" - Scaling sell executed
- "Order successful: {...}" - Trade completed
- "New peak reached: X" - Peak tracking update  
- "System reset - back to ADVANCE phase" - Full cycle completed
```

**Monitor Logs:**
```bash
# Watch strategy activity in real-time
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Strategy logs appear in console output
```

**Strategy State Structure:**
```json
{
  "symbol": "PURR/USDC:USDC",
  "unit_size": 0.1,
  "entry_price": 5.12,
  "current_unit": 2,
  "peak_unit": 5,
  "valley_unit": null,
  "phase": "RETRACEMENT",
  "long_invested": 40.0,
  "long_cash": 10.0,
  "hedge_short": 0.0,
  "last_price": 5.32,
  "position_size_usd": 50.0
}
```

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation with:

- All endpoints documented
- Request/response examples
- Try-it-now functionality

## � Important Testnet Notes

1. **Always Verify Testnet Mode:**

   - Ensure `HYPERLIQUID_TESTNET=true` in `.env`
   - Check logs show "testnet" in connection messages

2. **Test Funds:**

   - Use testnet faucet for USDC
   - Start with small amounts ($10-100) for testing

3. **API Rate Limits:**

   - HyperLiquid has rate limits even on testnet
   - System includes built-in rate limiting

4. **Data Persistence:**
   - All trades and states saved to database
   - Safe to restart server - state resumes automatically

## ⚠️ Troubleshooting

### Common Issues

**"Failed to initialize exchange":**
- Verify `HYPERLIQUID_TESTNET=true` in `.env`
- Check `HYPERLIQUID_BASE_URL=https://api.hyperliquid-testnet.xyz`
- Ensure testnet wallet has funds

**"No active strategy found":**
- Start strategy first via `/strategy/start` endpoint
- Check if `strategy_state.json` exists in backend directory

**"Order must have minimum value of $10":**
- Increase order size to meet minimum requirements
- Use position_size_usd >= 50 for strategy testing

**"hyperliquid market orders require price":**
- This is automatically handled by the API now
- Market orders include automatic slippage calculation

### Debug Mode

Enable detailed logging:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

This provides verbose output for all operations.

## =� Next Steps

1. **Test Strategy Performance:** Run multiple scenarios with different market conditions
2. **Monitor Allocation Changes:** Track how system responds to price movements
3. **Verify Reset Mechanism:** Test portfolio growth and unit scaling
4. **Prepare for Mainnet:** When ready, set up dedicated HyperLiquid account

## =� Production Readiness

Before moving to mainnet:

- [ ] Set up dedicated HyperLiquid account
- [ ] Update authentication to proper wallet format
- [ ] Set `HYPERLIQUID_TESTNET=false`
- [ ] Implement additional monitoring/alerts
- [ ] Test with small real funds first

---

**� Remember: This is testnet - no real money at risk!** Use this environment to fully understand and test the 4-phase strategy before any mainnet deployment.

## 📚 **README Maintenance Instructions**

**⚠️ Important**: When making changes to the API, always update this README file to keep documentation current.

### When to Update This File:

1. **New API Endpoints**: Add curl examples to the appropriate sections
2. **Modified Request/Response Formats**: Update existing curl commands
3. **New Environment Variables**: Add to the Configuration section
4. **New Log Files or Debugging Tools**: Update the Monitoring & Debugging section
5. **Changed Installation Steps**: Update Prerequisites or Installation sections

### How to Update:

1. **Test all curl commands** after making API changes
2. **Use the correct port** (currently 3000, may change)
3. **Include realistic example data** in curl commands
4. **Add new sections** in logical order (before troubleshooting)
5. **Keep examples simple** but functional

### Testing Your Updates:

```bash
# Start the server
uv run python -m app.main

# Test each curl command in the README
# Example:
curl "http://localhost:8000/api/v1/exchange/positions"
```

### Markdown Formatting:

- Use **bold** for important terms
- Use `code blocks` for commands and code
- Use **bash** code blocks for shell commands
- Keep sections organized with proper headers
- Focus on curl commands and backend API examples
