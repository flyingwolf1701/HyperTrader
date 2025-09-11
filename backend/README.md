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
uv run python src/main.py --symbol ETH --wallet long --unit-size 25.0 --position-size 1000 --leverage 10 --testnet
```

**Utility:**
```bash
cd backend
uv run python scripts/hl_commands.py status
uv run python scripts/hl_commands.py close SOL
```