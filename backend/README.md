# HyperTrader

```bash
cd backend
uv run python src/main.py --symbol SOL --wallet long --unit-size 5.0 --position-size 200 --leverage 10 --testnet
```

**Parameters:**
- `--unit-size`: USD per unit (5.0 = $5 price moves)
- `--position-size`: Position value in USD (200 = $200 position)

**Full example:**
```bash
cd backend
uv run python src/main.py --symbol SOL --wallet long --unit-size 0.5 --position-size 2000 --leverage 20 --testnet
uv run python src/main.py --symbol BTC --wallet long --unit-size 25 --position-size 20000 --leverage 40 --testnet
uv run python src/main.py --symbol ETH --wallet long --unit-size 1 --position-size 12500 --leverage 25 --testnet
```

**Utility:**
```bash
cd backend
uv run python scripts/hl_commands.py status
uv run python scripts/hl_commands.py close SOL
```

## Initial Prompt for Claude to study and gain context. 
Please read docs\strategy_doc_v9.md and docs\data_flow.md for context on the app. Then read backend\src\main.py, and files in these folders: backend\src\core, backend\src\exchange, backend\src\strategy.

## Unit Tests

The test suite ensures your trading bot works correctly without needing to run on testnet first.

### Quick Start
```bash
cd backend

# Run all tests
uv run python -m pytest tests/ -v

# Run core functionality tests (fastest, recommended for quick checks)
uv run python -m pytest tests/test_simple.py -v

# Run with coverage
uv run python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Test Files Overview

| Test File | Description | Tests |
|-----------|-------------|--------|
| `test_simple.py` | Core functionality (all passing) | 9 tests |
| `test_buy_orders.py` | Buy order placement verification | 6 tests |
| `test_data_models.py` | Data structures with hypothesis | 14 tests |
| `test_unit_tracker.py` | Sliding window management | Full coverage |
| `test_position_map.py` | Position tracking functions | Full coverage |
| `test_integration.py` | End-to-end order flow | Integration |

### Running Specific Tests

```bash
# Test buy order logic (important after recent fix)
uv run python -m pytest tests/test_buy_orders.py -v

# Test with detailed output
uv run python -m pytest tests/test_simple.py -v --tb=short

# Run with hypothesis statistics
uv run python -m pytest tests/ --hypothesis-show-statistics
```

### Coverage Reports

```bash
# Generate terminal coverage report
uv run python -m pytest tests/test_simple.py --cov=src/strategy --cov-report=term-missing

# Generate HTML coverage report
uv run python -m pytest tests/test_simple.py --cov=src/strategy --cov-report=html

# View HTML report
# Open backend/htmlcov/index.html in browser
```

**Current Coverage:** 83% for strategy module

### Test Configuration Files
- `.coveragerc` - Coverage settings
- `tests/conftest.py` - Fixtures and mocks
- `pyproject.toml` - pytest configuration