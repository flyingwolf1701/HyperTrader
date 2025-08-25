# HyperTrader Backend - Stage 1 & 2 Complete

WebSocket-based price tracking system with unit change detection for the HyperTrader automated trading strategy on Hyperliquid testnet.

## ✅ Completed: Stage 1 & 2

### Stage 1: WebSocket Connection & Price Logging
- **Real-time WebSocket connection** to Hyperliquid testnet
- **Live price tracking** with trade size information
- **Stable connection handling** with proper disconnection

### Stage 2: Unit Change Tracking  
- **Decimal-based calculations** - No float precision issues
- **Peak and valley tracking** - Tracks highest and lowest units reached
- **Phase system** - ADVANCE, RETRACEMENT, DECLINE, RECOVERY phases ready
- **Unit distance calculations** - Units from peak/valley for phase transitions
- **Full test coverage** - 10 pytest tests, all passing

## Quick Start

### Prerequisites
- Python 3.13+
- `uv` package manager
- Hyperliquid testnet account (for future stages)

### Installation

```bash
cd backend
uv sync
```

### Configuration

The `.env` file is already configured:
```env
# HyperLiquid API Configuration (Testnet)
HYPERLIQUID_WALLET_KEY=0x329C49392608175A071fC9AF982fF625f119fFAE
HYPERLIQUID_PRIVATE_KEY=redacted
HYPERLIQUID_TESTNET=true

# Trading Configuration
DEFAULT_LEVERAGE=10
UNIT_PERCENTAGE=0.10
```

## Running the System

### Basic Usage (Run Indefinitely)

```bash
uv run python main.py
```

This will:
- Connect to Hyperliquid testnet WebSocket
- Subscribe to ETH trades
- Display real-time prices with trade size
- Track unit changes (default: $2 per unit)
- Show phase information on unit changes
- Track peak and valley units

Press `Ctrl+C` to stop.

### Run with Custom Parameters

```bash
# Run for specific duration (in minutes)
uv run python main.py --duration 5

# Track different symbol
uv run python main.py --symbol BTC

# Use custom unit size
uv run python main.py --unit-size 5.0

# Combine parameters
uv run python main.py --symbol ETH --unit-size 10.0 --duration 10
```

### Run Tests

```bash
# Run all unit tracker tests
uv run pytest tests/test_unit_tracker.py -v

# Run with coverage
uv run pytest tests/test_unit_tracker.py --cov=src --cov-report=term-missing
```

## Expected Output

```
============================================================
HyperTrader Stage 1 & 2 - Price Tracking with Unit Detection
Symbol: ETH
Unit Size: $2.0
Duration: Indefinite
============================================================
[14:17:53] INFO | Connecting to Hyperliquid WebSocket...
[14:17:53] INFO | Successfully connected to Hyperliquid WebSocket
[14:17:53] INFO | Subscribed to ETH trades with unit size $2.0
[14:17:53] INFO | [14:17:53] ETH Price: $4466.70 | Size: 0.0034 | Unit: 0
[14:17:53] INFO | Entry price set to: $4466.70
[14:17:53] INFO | [14:17:53] ETH Price: $4488.90 | Size: 0.0033 | Unit: 0
[14:17:53] INFO | *** UNIT CHANGE: 0 -> 11 ***
[14:17:53] INFO | ETH Phase Info - Phase: ADVANCE | Peak: 11 | Valley: 0 | Units from Peak: 0 | Units from Valley: 11
```

## Unit Tracking Logic

### Core Implementation
- **Entry Price**: Automatically set on first received price
- **Unit Size**: Configurable (default $2.00)
- **Unit Calculation**: `current_unit = int((current_price - entry_price) / unit_size)`
- **Decimal Precision**: All prices use Python's Decimal type for accuracy

### Example Scenarios
- Entry: $4466.70
- Price rises to $4468.70 → Unit: +1 (up $2)
- Price rises to $4476.70 → Unit: +5 (up $10)
- Price falls to $4464.70 → Unit: -1 (down $2)
- Price falls to $4456.70 → Unit: -5 (down $10)

### Phase Information Tracked
- **Current Phase**: ADVANCE (default, ready for other phases)
- **Peak Unit**: Highest unit reached (for RETRACEMENT detection)
- **Valley Unit**: Lowest unit reached (for RECOVERY detection)
- **Units from Peak**: Current distance from peak (triggers phase changes)
- **Units from Valley**: Current distance from valley (triggers recovery)

## Project Structure

```
backend/
├── .env                      # Environment configuration
├── README.md                 # This file
├── pyproject.toml           # Python dependencies
├── main.py                  # Main entry point with argument parsing
├── src/                     # Core modules
│   ├── __init__.py         # Package init
│   ├── config.py           # Settings and configuration
│   ├── models.py           # UnitTracker, Phase enum
│   └── websocket_client.py # HyperliquidWebSocketClient
├── tests/                   # Test suite
│   ├── __init__.py         # Test package init
│   └── test_unit_tracker.py # Comprehensive unit tests
└── logs/                    # Log files (auto-created)
    └── price_tracker.log   # Rotating log file
```

## API Documentation

### HyperliquidWebSocketClient
Main WebSocket client for real-time price tracking.

**Methods:**
- `connect()` - Establish WebSocket connection
- `disconnect()` - Close connection gracefully
- `subscribe_to_trades(symbol, unit_size)` - Subscribe to trades with unit tracking
- `listen()` - Main event loop for processing messages

### UnitTracker
Tracks unit changes and phase information.

**Properties:**
- `entry_price: Decimal` - Entry price (set on first price)
- `unit_size: Decimal` - Price movement per unit
- `current_unit: int` - Current unit position
- `peak_unit: int` - Highest unit reached
- `valley_unit: int` - Lowest unit reached
- `phase: Phase` - Current trading phase

**Methods:**
- `calculate_unit_change(price)` - Calculate and update unit position
- `get_units_from_peak()` - Distance from peak (for retracement)
- `get_units_from_valley()` - Distance from valley (for recovery)

## Development Plan Progress

- [x] **Stage 1**: WebSocket Connection & Price Logging ✅
- [x] **Stage 2**: Unit Change Tracking ✅
- [ ] **Stage 3**: CCXT Exchange Integration & Validation
- [ ] **Stage 4**: "Enter Trade" & ADVANCE Phase Implementation
- [ ] **Stage 5**: RETRACEMENT Phase Implementation
- [ ] **Stage 6**: RESET Mechanism Implementation
- [ ] **Stage 7**: DECLINE Phase Implementation
- [ ] **Stage 8**: RECOVERY Phase Implementation

## Next: Stage 3 - CCXT Integration

Stage 3 will add exchange integration for:
- Account balance fetching
- Position data retrieval
- Market order execution
- Integration with unit tracking for automated trading

## Troubleshooting

### "ModuleNotFoundError: No module named 'websockets'"
Always use `uv run` to execute scripts:
```bash
uv run python main.py  # ✅ Correct
python main.py         # ❌ Wrong
```

### No price updates showing
- Check internet connection
- Verify Hyperliquid testnet is operational
- Check logs in `logs/price_tracker.log`

### Unit changes seem wrong
- Verify entry price is set (shown in first price message)
- Check unit size parameter (default $2)
- Remember: Price must move full unit size to trigger change

---

**⚠️ Testnet Only** - Currently configured for Hyperliquid testnet. No real funds at risk.