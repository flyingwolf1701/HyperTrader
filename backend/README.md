# HyperTrader Backend

Advanced crypto trading bot implementing a sophisticated 4-phase hedging strategy on HyperLiquid DEX. This system automatically manages long/hedge allocations based on price movements, providing downside protection while capturing upside gains.

## =� Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL database (Neon recommended)
- HyperLiquid testnet account

### Installation

1. **Clone and navigate to backend:**

   ```bash
   cd backend
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Start the server:**
   ```bash
   uv run python -m app.main
   ```

The API will be available at `http://localhost:8000` with docs at `http://localhost:8000/docs`.

## =' Configuration

### Environment Variables (.env)

```env
# Database Configuration
DATABASE_URL=postgresql://your_db_connection_string

# HyperLiquid API Configuration (Testnet)
HYPERLIQUID_WALLET_KEY=your_HYPERLIQUID_WALLET_KEY_here
HYPERLIQUID_PRIVATE_KEY=your_HYPERLIQUID_PRIVATE_KEY_here
HYPERLIQUID_TESTNET=true  # KEEP TRUE FOR TESTING

# Application Settings
DEBUG=true
API_PORT=3000
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

## <� Testing the System

### 1. Start the Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Expected output:

```
INFO:app.main:Starting HyperTrader backend...
INFO:app.db.session:Database connection initialized
INFO:app.services.exchange:Loaded 1279 markets
INFO:app.services.exchange:ExchangeManager initialized successfully
INFO:app.main:Exchange manager initialized
INFO:     Application startup complete.
```

### 2. Test API Endpoints

**Health Check:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","app":"HyperTrader"}
```

**Get Available Markets:**

```bash
curl http://localhost:8000/api/v1/exchange/pairs
# Returns list of available trading pairs
```

**Get Current Price:**

```bash
curl "http://localhost:8000/api/v1/exchange/price/BTC%2FUSDC"
# Returns current BTC price
```

### 3. Start a Trading Plan

**Create a new trading plan:**

```bash
curl -X POST "http://localhost:8000/api/v1/trade/start" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDC",
    "position_size_usd": 100.0,
    "leverage": 10
  }'
```

This will:

- Place initial buy order on testnet
- Create SystemState with 50/50 allocation split
- Start tracking price movements
- Return trading plan ID

### 4. Monitor Real-Time Trading

**WebSocket Connection:**

```bash
# WebSocket endpoint for real-time trading data
# ws://localhost:8000/ws/BTC%2FUSDC

# Note: WebSocket connections require a WebSocket client
# You can use tools like wscat for testing:
# npm install -g wscat
# wscat -c "ws://localhost:8000/ws/BTC%2FUSDC"
```

### 5. Check Trading State

**Get current state:**

```bash
curl "http://localhost:8000/api/v1/trade/state/BTC%2FUSDC"
```

Returns comprehensive state including:

- Current phase (advance/retracement/decline/recovery)
- Unit positions and tracking
- Allocation percentages
- Unrealized P&L

### 6. Monitor Live Positions & Trades

**Check all open positions:**

```bash
curl "http://localhost:8000/api/v1/exchange/positions"
```

**Check position for specific symbol:**

```bash
curl "http://localhost:8000/api/v1/exchange/positions/BTC%2FUSDC"
```

**Get comprehensive position summary:**

```bash
curl "http://localhost:8000/api/v1/exchange/position-summary"
```

**View recent trades:**

```bash
# Last 24 hours, up to 50 trades
curl "http://localhost:8000/api/v1/exchange/trades"

# Last 6 hours for specific symbol
curl "http://localhost:8000/api/v1/exchange/trades?symbol=BTC%2FUSDC&hours_back=6&limit=20"
```

**Check open orders:**

```bash
# All open orders
curl "http://localhost:8000/api/v1/exchange/open-orders"

# Open orders for specific symbol
curl "http://localhost:8000/api/v1/exchange/open-orders?symbol=BTC%2FUSDC"
```

**View account balances:**

```bash
curl "http://localhost:8000/api/v1/exchange/balances"
```

## >� 4-Phase Strategy Testing

### Understanding the Phases

**ADVANCE Phase:**

- Both allocations 100% long
- Building positions during uptrends
- Tracking peak prices

**RETRACEMENT Phase:**

- Hedge scales down immediately on unit drops
- Long waits for 2-unit confirmation
- 25% scaling per unit movement

**DECLINE Phase:**

- Long allocation 100% cash (protection)
- Hedge allocation 100% short (profit from decline)
- Positions held to compound gains

**RECOVERY Phase:**

- Systematic re-entry from valleys
- Hedge unwinds shorts immediately
- Long re-enters with confirmation

### Test Scenarios

**Test 1: Basic Price Movement**

1. Start trading plan with small amount (e.g., $10)
2. Monitor phase transitions as price moves
3. Verify allocations adjust correctly

**Test 2: Peak Tracking**

1. Watch for new highs setting peak_unit
2. Verify retracement scaling when price drops
3. Check confirmation delays for long allocation

**Test 3: System Reset**

1. Let strategy reach reset conditions (longCash=0, hedgeShort=0)
2. Verify portfolio value recalculation
3. Check fresh unit/phase initialization

## =� Monitoring & Debugging

### Enhanced Logging System

The application now uses **Loguru** for advanced logging with automatic file rotation and structured logging:

**Log Files:**
```bash
# Main application log (all events)
tail -f logs/hypertrader.log

# Trade-specific events only
tail -f logs/trading.log

# WebSocket price feed events
tail -f logs/websocket.log

# Errors only for quick troubleshooting
tail -f logs/errors.log
```

**Search Trading Events:**
```bash
# Find all trade executions
grep "TRADE:" logs/trading.log

# Find specific symbol activity
grep "BTC/USDC" logs/trading.log

# Find phase transitions
grep "Phase transition" logs/trading.log

# Find order placement attempts
grep "Placing.*order" logs/trading.log
```

**Log Features:**
- **Auto-rotation**: Files rotate when they reach size limits (10-50MB)
- **Compression**: Old logs are automatically compressed
- **Retention**: Logs kept for 3-30 days depending on type
- **Symbol context**: Trade logs include symbol information
- **Async logging**: Non-blocking performance

### Database Queries

```sql
-- View active trading plans
SELECT symbol, current_phase, created_at FROM trading_plans WHERE is_active = 'active';

-- Check system state details
SELECT symbol, system_state->'current_unit' as unit,
       system_state->'current_phase' as phase
FROM trading_plans;
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

## =

Troubleshooting

### Common Issues

**"Failed to initialize exchange":**

- Check API credentials in `.env`
- Verify testnet access and funds

**"Database connection failed":**

- Verify DATABASE_URL is correct
- Ensure database is accessible

**"No active trading plan found":**

- Create trading plan first via `/trade/start` endpoint
- Check database for existing plans

**WebSocket connection issues:**

- Ensure trading plan exists for symbol
- Check server logs for specific errors

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
