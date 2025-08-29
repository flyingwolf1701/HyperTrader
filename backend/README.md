# HyperTrader - Simplified Long-Only Strategy v2.0

## Overview

HyperTrader implements an automated long-only strategy that scales positions during market volatility through four phases (ADVANCE, RETRACEMENT, DECLINE, RECOVERY) with an automatic RESET mechanism to compound profits.

**Key Simplification**: This version removes all short position complexity while preserving the core retracement scaling and compound growth logic.

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
# Start the simplified strategy
uv run python main.py trade ETH/USDC:USDC 2500 25 --leverage 25
```

This will:
1. Open a $2500 long position with 25x leverage
2. Start real-time price monitoring
3. Execute simplified scaling strategy automatically as price moves

## Simplified Strategy Logic

### Core Concept
Instead of complex long+short hedging, this version simply **scales the long position up and down** based on market movements:

- **Rising markets**: Hold 100% long position
- **Falling markets**: Sell fragments to reduce exposure (25% at a time)  
- **Recovery**: Buy back fragments to rebuild position
- **Compound growth**: RESET mechanism captures gains for next cycle

## Strategy Phases Explained

### 1. ADVANCE Phase
- **Trigger**: Price increases by one unit ($25)
- **Action**: Track peaks, lock 25% fragments when new peak reached
- **Portfolio**: 100% Long

### 2. RETRACEMENT Phase  
- **Trigger**: Price drops from peak
- **Actions by units from peak**:
  - `-1`: Hold position (no action)
  - `-2`: Sell 25% fragment (reduce exposure)
  - `-3`: Sell 25% fragment (reduce exposure)
  - `-4`: Sell 25% fragment (reduce exposure)
  - `-5`: Sell remaining position → 100% cash

### 3. VALLEY TRACKING
- **Condition**: Portfolio is 100% cash
- **Action**: Track lowest point (valley) for recovery signal

### 4. RECOVERY Phase
- **Trigger**: Price rises +2 units from valley
- **Actions**:
  - `+2`: Buy back 25% fragment
  - `+3`: Buy back 25% fragment  
  - `+4`: Buy back 25% fragment
  - `+5`: Buy back final 25% → 100% long → RESET

### 5. RESET Mechanism
- **Trigger**: Position becomes 100% long after complete cycle
- **Action**: Lock in profits as new baseline, restart with larger position

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
uv run python main.py trade ETH/USDC:USDC 2500 2 --leverage 25
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

The simplified strategy aims to:
- **Profit during uptrends**: Hold 100% long positions during ADVANCE phase
- **Reduce risk during retracements**: Scale down position by selling fragments  
- **Preserve capital during declines**: Hold cash during valley periods
- **Capitalize on recovery**: Rebuild position during RECOVERY phase
- **Compound returns**: RESET mechanism captures gains and starts next cycle with larger base

**Key Benefits of Simplification**:
- ✅ No position netting issues (single wallet, long-only)
- ✅ Easier to understand and monitor
- ✅ Preserves core compound growth mechanism
- ✅ Works perfectly with Hyperliquid's position management
- ✅ Still provides risk management through position scaling

Expected outcome: Steady compound growth through market cycles with reduced complexity and operational risk.