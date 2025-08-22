import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings

def configure_logging():
    """
    Configure loguru for the HyperTrader application with file and console logging.
    """
    # Remove default handler
    logger.remove()
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Console logging with colors and nice formatting
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True
    )
    
    # Main application log file - auto-rotating
    logger.add(
        logs_dir / "hypertrader.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="50 MB",  # Rotate when file reaches 50MB
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress old logs
        enqueue=True,  # Thread-safe async logging
        catch=True  # Catch exceptions in logged functions
    )
    
    # Trading-specific log file
    def trading_format(record):
        symbol = record.get("extra", {}).get("symbol", "SYSTEM")
        return f"{record['time']:YYYY-MM-DD HH:mm:ss.SSS} | {record['level'].name: <8} | {symbol} | {record['message']}\n"
    
    logger.add(
        logs_dir / "trading.log",
        level="INFO",
        format=trading_format,
        filter=lambda record: "TRADE" in record["message"] or record.get("extra", {}).get("trade_event"),
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True
    )
    
    # Error-only log file
    logger.add(
        logs_dir / "errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True
    )
    
    # WebSocket events log
    def websocket_format(record):
        symbol = record.get("extra", {}).get("symbol", "WS")
        return f"{record['time']:YYYY-MM-DD HH:mm:ss.SSS} | {record['level'].name: <8} | {symbol} | {record['message']}\n"
    
    logger.add(
        logs_dir / "websocket.log",
        level="DEBUG",
        format=websocket_format,
        filter=lambda record: "websocket" in record.get("extra", {}).get("component", "").lower() or "WS" in record["message"],
        rotation="25 MB",
        retention="3 days",
        compression="zip",
        enqueue=True
    )
    
    logger.info("Loguru logging configured successfully")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Logs directory: {logs_dir.absolute()}")

def get_trade_logger(symbol: str):
    """
    Get a logger bound with trading symbol for structured logging.
    
    Args:
        symbol: Trading symbol (e.g., "BTC/USDC")
        
    Returns:
        Loguru logger with symbol context
    """
    return logger.bind(symbol=symbol, trade_event=True)

def get_websocket_logger(symbol: str):
    """
    Get a logger bound for WebSocket events.
    
    Args:
        symbol: Trading symbol (e.g., "BTC/USDC")
        
    Returns:
        Loguru logger with WebSocket context
    """
    return logger.bind(symbol=symbol, component="websocket")

# Log rotation and cleanup utilities
def cleanup_old_logs(days_to_keep: int = 7):
    """
    Manually cleanup logs older than specified days.
    
    Args:
        days_to_keep: Number of days to retain logs
    """
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return
        
    import time
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    
    for log_file in logs_dir.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            log_file.unlink()
            logger.info(f"Cleaned up old log file: {log_file}")

# Intercept standard logging messages and redirect to loguru
class InterceptHandler:
    """
    Intercept standard logging messages and redirect them to loguru.
    """
    def __init__(self, level=0):
        self.level = level
    
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == __file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_standard_logging_intercept():
    """
    Setup interception of standard Python logging to redirect to loguru.
    """
    import logging
    
    # Remove all handlers from root logger
    logging.root.handlers = []
    
    # Add our intercept handler
    logging.root.addHandler(InterceptHandler())
    
    # Set logging level
    logging.root.setLevel(logging.DEBUG)
    
    # Intercept specific loggers that might be used by dependencies
    for logger_name in ["uvicorn", "fastapi", "sqlalchemy", "ccxt"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.addHandler(InterceptHandler())
        logging_logger.propagate = False