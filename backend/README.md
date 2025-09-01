# HyperTrader - Professional Hyperliquid Trading CLI

## Overview

HyperTrader is a professional command-line interface for trading on the Hyperliquid decentralized exchange. Built with the official Hyperliquid SDK, it provides reliable trading operations with support for both main wallet and sub-wallet management.

## Features

- **Full Trading Operations**: Open long/short positions with leverage
- **Multi-Wallet Support**: Trade on main wallet or sub-wallets
- **Real-time Market Data**: Get current prices and position tracking
- **Position Management**: Monitor and close positions with detailed PnL
- **Testnet/Mainnet**: Safe testing environment with mainnet support

## Quick Start

### Prerequisites

```bash
# Install UV package manager
pip install uv

# Install dependencies
cd backend
uv sync
```

### Configuration

Create a `.env` file in the backend directory:

```env
# Wallet Configuration
HYPERLIQUID_WALLET_KEY=0x329C49392608175A071fC9AF982fF625f119fFAE
HYPERLIQUID_TESTNET_PRIVATE_KEY=your_private_key_here

# Sub-wallet (optional)
HYPERLIQUID_TESTNET_SUB_WALLET_LONG=0x672e85f00bda872dcf16b9d65d35d4271e2610cb

# Network
HYPERLIQUID_TESTNET=true
```

## Commands

### Check Account Status

```bash
# View main wallet status
uv run python main.py status

# View sub-wallet status  
uv run python main.py status --sub-wallet

# Output shows:
# - Network (testnet/mainnet)
# - Wallet address
# - Account balance (total, margin used, available)
# - Open positions with PnL
```

### Open Trading Positions

```bash
# Open a long position
uv run python main.py trade ETH 100 --leverage 10

# Open a short position
uv run python main.py trade ETH 100 --short --leverage 10

# Trade on sub-wallet
uv run python main.py trade ETH 100 --sub-wallet --leverage 10

# Parameters:
# - Symbol: ETH, BTC, SOL, etc.
# - Amount: Position size in USD
# - --leverage: 1-25x (default: 10)
# - --short: Open short position (default: long)
# - --sub-wallet: Use sub-wallet
```

### Close Positions

```bash
# Close a position
uv run python main.py close ETH

# Close without confirmation prompt
uv run python main.py close ETH --force

# Close on sub-wallet
uv run python main.py close ETH --sub-wallet
```

### Get Market Prices

```bash
# Get current price for a symbol
uv run python main.py price ETH
uv run python main.py price BTC
```

### Switch Wallets

```bash
# Switch to sub-wallet
uv run python main.py switch sub

# Switch back to main wallet
uv run python main.py switch main
```

### Global Options

```bash
# Enable verbose logging
uv run python main.py -v status

# Use mainnet (CAREFUL - real funds!)
uv run python main.py --mainnet status
```

## Example Trading Session

```bash
# 1. Check initial status
uv run python main.py status

# 2. Get current ETH price
uv run python main.py price ETH

# 3. Open a long position with 10x leverage
uv run python main.py trade ETH 100 --leverage 10

# 4. Monitor position
uv run python main.py status

# 5. Close position when profitable
uv run python main.py close ETH
```

## Sub-Wallet Trading

Sub-wallets allow isolated position management:

```bash
# Check sub-wallet status
uv run python main.py status --sub-wallet

# Open position on sub-wallet
uv run python main.py trade ETH 50 --sub-wallet --leverage 5

# Close sub-wallet position
uv run python main.py close ETH --sub-wallet
```

## Architecture

### Core Components

- **`hyperliquid_sdk.py`**: Clean wrapper around official Hyperliquid SDK
- **`main.py`**: CLI application with command routing
- **`hl_commands.py`**: Legacy command implementation (reference)

### SDK Features

The `HyperliquidClient` class provides:

- Account balance retrieval
- Position management (open/close/monitor)
- Market data access
- Leverage configuration
- Multi-wallet support

## Safety Features

- **Testnet by Default**: Safe testing environment
- **Confirmation Prompts**: Requires confirmation for mainnet trades
- **Position Validation**: Checks for existing positions before operations
- **Error Handling**: Comprehensive error messages and recovery

## Troubleshooting

### Common Issues

1. **"No module named 'requests'"**
   ```bash
   uv add requests
   ```

2. **"No position to close"**
   - Verify position exists: `uv run python main.py status`
   - Check correct wallet (main vs sub)

3. **Authentication Errors**
   - Verify private key in `.env`
   - Ensure wallet address matches private key
   - Check testnet/mainnet setting

4. **Insufficient Balance**
   - Check available balance: `uv run python main.py status`
   - Reduce position size or leverage

### API Key vs Direct Wallet

The system automatically detects if you're using:
- **Direct Wallet**: Private key matches wallet address
- **API Key**: Private key is an agent that trades on behalf of main wallet

## Testing

### Testnet Testing

```bash
# Safe testing with testnet funds
uv run python main.py trade ETH 100 --leverage 10

# Monitor results
uv run python main.py status
```

### Production Deployment

⚠️ **WARNING**: Only use mainnet after thorough testing

```bash
# Mainnet trading (requires confirmation)
uv run python main.py --mainnet trade ETH 1000 --leverage 5
```

## Advanced Usage

### Verbose Logging

```bash
# Enable detailed logging
uv run python main.py -v trade ETH 100
```

### Programmatic Usage

```python
from src.exchange.hyperliquid_sdk import HyperliquidClient

# Initialize client
client = HyperliquidClient(use_testnet=True)

# Get balance
balance = client.get_balance()
print(f"Available: ${balance.available}")

# Open position
result = client.open_position(
    symbol="ETH",
    usd_amount=Decimal("100"),
    is_long=True,
    leverage=10
)
```

## Support

### Logs
- Console output with timestamps
- Color-coded log levels
- Verbose mode for debugging

### State Management
- Positions tracked in real-time
- Automatic PnL calculation
- Multi-wallet state isolation

## Performance

The new architecture provides:
- ✅ Fast execution with official SDK
- ✅ Reliable order placement
- ✅ Accurate position tracking
- ✅ Clean error handling
- ✅ Professional CLI interface

## License

Private repository - All rights reserved