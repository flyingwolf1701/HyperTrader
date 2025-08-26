@echo off
REM HyperTrader Strategy Runner for Windows
REM Runs the strategy with automatic restart on failure

set SYMBOL=ETH/USDC:USDC
set POSITION_SIZE=1000
set UNIT_SIZE=2.0
set LEVERAGE=10

echo ==================================
echo Starting HyperTrader Strategy
echo Symbol: %SYMBOL%
echo Position Size: $%POSITION_SIZE%
echo Unit Size: $%UNIT_SIZE%
echo Leverage: %LEVERAGE%x
echo ==================================

:restart
echo [%date% %time%] Starting strategy...

REM Run the strategy
uv run python hypertrader.py %SYMBOL% %POSITION_SIZE% %UNIT_SIZE% --leverage %LEVERAGE%

REM Check if it crashed
if %errorlevel% neq 0 (
    echo [%date% %time%] Strategy crashed with code %errorlevel%
    echo [%date% %time%] Restarting in 30 seconds...
    timeout /t 30
    goto restart
)

echo [%date% %time%] Strategy exited normally
pause