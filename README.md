# HyperTrader

Advanced crypto trading bot with hedging strategy for HyperLiquid exchange.

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- UV package manager for Python
- Bun for frontend (optional, can use npm/yarn)

### Backend Setup

1. **Navigate to backend directory:**

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

4. **Run the backend:**

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 3001 --log-level info
   ```

5. **Test the connection:**

   ```bash
   # Root endpoint
   curl http://localhost:3001/
   # Response: {"message":"HyperTrader API is running"}

   # Health check
   curl http://localhost:3001/health
   # Response: {"status":"healthy","app":"HyperTrader"}
   ```

### Frontend Setup

1. **Navigate to frontend directory:**

   ```bash
   cd frontend
   ```

2. **Install dependencies:**

   ```bash
   bun install
   # or npm install
   ```

3. **Run the frontend:**

   ```bash
   bun dev
   # or npm run dev
   ```

4. **Access the UI:**
   Open http://localhost:3000 in your browser

## Configuration

### Backend Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

```env
# Database Configuration
DATABASE_URL=your_postgresql_connection_string

# HyperLiquid API Configuration
HYPERLIQUID_WALLET_KEY=your_api_key
HYPERLIQUID_PRIVATE_KEY=your_secret_key
HYPERLIQUID_TESTNET=true

# Trading Configuration
SYMBOL=LINK
DEFAULT_LEVERAGE=10

# Logging
LOG_LEVEL=INFO
```

### Testing Database & Exchange Connection

When you start the backend, you should see:

```
INFO:app.main:Starting HyperTrader backend...
INFO:app.db.session:Database connection initialized successfully
INFO:app.db.session:Database tables created/verified
INFO:app.services.exchange:ExchangeManager initialized with 1282 markets.
INFO:app.main:Exchange manager initialized
INFO:     Uvicorn running on http://0.0.0.0:3001
```

This confirms:

- ✅ Database connection working
- ✅ Tables created/verified
- ✅ HyperLiquid exchange connection working
- ✅ API server running

## Development

### Running Tests

**Backend:**

```bash
cd backend
uv run pytest
```

**Frontend:**

```bash
cd frontend
bun test
# or npm test
```

### Project Structure

```
HyperTrader/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/       # API endpoints
│   │   ├── core/      # Configuration
│   │   ├── db/        # Database setup
│   │   ├── models/    # Database models
│   │   ├── services/  # Business logic
│   │   └── schemas/   # Pydantic schemas
│   └── tests/         # Backend tests
├── frontend/          # Nuxt.js frontend
│   ├── components/    # Vue components
│   ├── composables/   # Vue composables
│   ├── pages/         # Route pages
│   └── types/         # TypeScript types
└── docs/              # Documentation
```

## Trading Strategy

HyperTrader implements a 4-phase hedging strategy:

1. **Advance Phase**: Both allocations long, tracking peaks
2. **Retracement Phase**: Scaling positions during decline from peak
3. **Decline Phase**: Long fully cashed, hedge fully short
4. **Recovery Phase**: Systematic re-entry during recovery

See `docs/strategy_doc.md` for detailed strategy explanation.

## Safety Features

- **Testnet Support**: Always test on HyperLiquid testnet first
- **High-Precision Math**: Decimal arithmetic prevents floating-point errors
- **Database Persistence**: State saved to PostgreSQL
- **Error Handling**: Comprehensive retry logic and error recovery
- **Logging**: Detailed logging for monitoring and debugging

## Troubleshooting

### Port Already in Use

If port 3001 is busy, change the port:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 3002 --log-level info
```

### Database Connection Issues

1. Verify DATABASE_URL in .env
2. Check PostgreSQL server is running
3. Ensure database credentials are correct

### Exchange Connection Issues

1. Verify HyperLiquid API credentials
2. Check HYPERLIQUID_TESTNET=true for testing
3. Ensure API key has required permissions

## Support

For issues and questions:

1. Check the logs for error messages
2. Verify environment configuration
3. Test individual components (DB, exchange) separately

## License

[Add your license here]
