#!/bin/bash
# HyperTrader Strategy Runner
# Runs the strategy with automatic restart on failure

SYMBOL="ETH/USDC:USDC"
POSITION_SIZE=1000
UNIT_SIZE=2.0
LEVERAGE=10

# Create logs directory if it doesn't exist
mkdir -p logs

echo "=================================="
echo "Starting HyperTrader Strategy"
echo "Symbol: $SYMBOL"
echo "Position Size: $POSITION_SIZE"
echo "Unit Size: $UNIT_SIZE"
echo "Leverage: ${LEVERAGE}x"
echo "=================================="

# Function to run the strategy
run_strategy() {
    while true; do
        echo "[$(date)] Starting strategy..."
        
        # Run the strategy
        uv run python hypertrader.py "$SYMBOL" "$POSITION_SIZE" "$UNIT_SIZE" --leverage "$LEVERAGE"
        
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo "[$(date)] Strategy exited normally"
            break
        else
            echo "[$(date)] Strategy crashed with code $EXIT_CODE"
            echo "[$(date)] Restarting in 30 seconds..."
            sleep 30
        fi
    done
}

# Trap signals for clean shutdown
trap 'echo "Shutdown requested"; exit 0' SIGINT SIGTERM

# Run the strategy
run_strategy