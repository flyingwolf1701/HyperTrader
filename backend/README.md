# HyperTrader - Advanced Hedging Strategy v6.0.0

## Overview

HyperTrader implements an automated hedging strategy that manages unified long/short/cash positions across multiple cryptocurrency assets on the Hyperliquid exchange. The strategy operates through four distinct phases (ADVANCE, RETRACEMENT, DECLINE, RECOVERY) with an automatic RESET mechanism to compound profits.

## Quick Start Guide

### Prerequisites

1. **Python Environment**
   ```bash
   # Ensure UV is installed
   pip install uv
   
   # Install dependencies
   uv sync
   ```

2. **Environment Configuration**
   Create a `.env` file in the backend directory:
   ```env
   HYPERLIQUID_WALLET_KEY=your_wallet_address
   HYPERLIQUID_PRIVATE_KEY=your_private_key
   HYPERLIQUID_TESTNET=true
   ```

3. **Network Selection**
   - **Testnet**: Use for testing (default, recommended)
   - **Mainnet**: Only after thorough testing

### Basic Commands

```bash
# Check current positions and balance
uv run python main.py check

# Start trading strategy (testnet)
uv run python main.py trade ETH/USDC:USDC 2500 5 --leverage 25

# Track prices with unit detection (no trading)
uv run python main.py track --symbol ETH --unit-size 5

# Close a position
uv run python main.py close ETH/USDC:USDC

# Monitor running strategies
uv run python main.py monitor
```

## Testing Configuration

For your current testing setup:
- **Symbol**: ETH/USDC:USDC
- **Position Size**: $2500
- **Unit Size**: $25 (smaller for testing)
- **Leverage**: 25x
- **Margin Required**: $100 ($2500 ÷ 25x)

### Start Your Test Trade

```bash
# Start the complete strategy
uv run python main.py trade ETH/USDC:USDC 2500 25 --leverage 25
```

This will:
1. Open a $2500 long position with 25x leverage
2. Start real-time price monitoring
3. Execute strategy phases automatically as price moves

## Strategy Phases Explained

### 1. ADVANCE Phase
- **Trigger**: Price increases by one unit ($25)
- **Action**: Track peak units, recalculate position fragments
- **Portfolio**: 100% Long

### 2. RETRACEMENT Phase
- **Trigger**: Price drops 1 unit from peak
- **Actions by units from peak**:
  - `-1`: Sell 1 fragment long → Open 1 fragment short
  - `-2`: Sell 2 fragments long → Add 1 fragment short
  - `-3`: Sell 2 fragments long → Add 1 fragment short  
  - `-4`: Sell 2 fragments long → Add 1 fragment short
  - `-5`: Sell remaining long → Add to short
  - `-6`: Enter DECLINE phase

### 3. DECLINE Phase
- **Condition**: ~50% short, ~50% cash
- **Action**: Hold defensive position, profit from further declines
- **Transition**: +2 units from valley → RECOVERY

### 4. RECOVERY Phase
- **Actions by units from valley**:
  - `+2` to `+4`: Close hedge fragments, buy long
  - `+5`: Close all short, convert to long
  - `+6`: 100% long → Trigger RESET

### 5. RESET Mechanism
- **Trigger**: Position becomes 100% long after complete cycle
- **Action**: Lock in profits as new baseline, restart cycle

## Alternative Testing Methods

### Using cURL (Direct API Testing)

If you want to test individual components without the full strategy:

```bash
# Check account balance
curl -X POST https://api.hyperliquid-testnet.xyz/info \
  -H "Content-Type: application/json" \
  -d '{"type": "clearinghouseState", "user": "YOUR_WALLET_ADDRESS"}'

# Get current ETH price
curl -X POST https://api.hyperliquid-testnet.xyz/info \
  -H "Content-Type: application/json" \
  -d '{"type": "allMids"}'

# Place a market order (requires signature)
# Note: Direct API orders require proper signing - use the Python client instead
```

### Manual Position Management

```bash
# Check current position
uv run python main.py check

# If you need to close a position manually
uv run python main.py close ETH/USDC:USDC

# Start fresh strategy
uv run python main.py trade ETH/USDC:USDC 2500 5 --leverage 25
```

## Monitoring Your Strategy

### Real-time Monitoring
```bash
# Start monitoring in separate terminal
uv run python main.py monitor
```

### Log Files
Strategy logs are saved to `logs/hypertrader_{timestamp}.log`

### Key Metrics to Watch
- **Current Phase**: Which phase the strategy is in
- **Current Unit**: Distance from entry price in units
- **Peak/Valley Units**: Historical extremes
- **Position Value**: Current position worth
- **Unrealized PnL**: Current profit/loss

## Troubleshooting

### Common Issues

1. **"No existing position" Error**
   - Make sure you have an open position before running certain commands
   - Use `python main.py check` to verify

2. **WebSocket Connection Issues**
   - Check internet connection
   - Verify Hyperliquid API status
   - Restart the strategy

3. **API Authentication Errors**
   - Verify wallet address and private key in `.env`
   - Ensure testnet setting matches your credentials

4. **Position Size Errors**
   - Check available balance with `python main.py check`
   - Reduce position size if insufficient margin

### Emergency Procedures

```bash
# Emergency stop - close all positions
uv run python main.py close ETH/USDC:USDC

# Check status after emergency stop
uv run python main.py check
```

## Configuration Files

- **`.env`**: API credentials and network settings
- **`config.yaml`**: Strategy parameters (optional)
- **`logs/`**: Strategy execution logs
- **`state/`**: Strategy state persistence (auto-created)

## Safety Features

- **Testnet by default**: Safe testing environment
- **Position limits**: Configurable maximum position sizes
- **Error handling**: Comprehensive error recovery
- **State persistence**: Automatic strategy state saving
- **Emergency stop**: Manual position closure capability

## Development and Testing

```bash
# Run in demo mode (no real trades)
uv run python main.py track --symbol ETH --unit-size 25 --duration 5

# Test specific functionality
uv run python -m pytest tests/ -v
```

## Production Deployment

⚠️ **WARNING**: Only use mainnet after extensive testnet validation

```bash
# For mainnet (CAREFUL!)
uv run python main.py trade ETH/USDC:USDC 2500 25 --leverage 25 --mainnet
```

## Support

- **Logs**: Check `logs/` directory for detailed execution logs
- **State**: Strategy state is auto-saved for crash recovery
- **Monitoring**: Use monitor command for real-time status

## Strategy Performance

The strategy aims to:
- **Profit during trends**: Long positions in ADVANCE phase
- **Protect during retracements**: Progressive hedging in RETRACEMENT
- **Profit from declines**: Short positions in DECLINE phase  
- **Capitalize on recovery**: Strategic re-entry in RECOVERY phase
- **Compound returns**: RESET mechanism locks in gains

Expected outcome: Net positive returns through complete market cycles while managing downside risk.