# HyperTrader

```bash
# start virtual environment

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

