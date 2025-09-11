"""
Configuration constants for HyperTrader Long Wallet Strategy
"""

from decimal import Decimal


class LongWalletConfig:
    """Configuration constants for long wallet strategy"""
    
    # Window configuration
    WINDOW_SIZE = 4  # Number of orders in sliding window
    WINDOW_TRAIL_DISTANCE = 4  # How many units behind/ahead to place orders
    INITIAL_WINDOW_UNITS = [-4, -3, -2, -1]  # Initial stop-loss positions
    
    # Fragment configuration
    FRAGMENT_PERCENT = Decimal("0.25")  # 25% per fragment
    NUM_FRAGMENTS = 4  # Total number of fragments
    
    # Order configuration
    POST_ONLY = True  # Use maker orders only for limit buys
    REDUCE_ONLY_STOPS = True  # Stop-losses only reduce position
    SLIPPAGE_TOLERANCE = Decimal("0.01")  # 1% slippage for market orders
    
    # Position limits
    MIN_ORDER_SIZE_USD = Decimal("10")  # Minimum order size in USD
    MAX_POSITION_SIZE_USD = Decimal("100000")  # Maximum position size in USD
    
    # Unit configuration
    DEFAULT_UNIT_RANGE = 20  # Pre-calculate units from -20 to +20
    MAX_UNITS_FROM_ENTRY = 100  # Maximum distance from entry point
    
    # Retry configuration
    MAX_ORDER_RETRIES = 3  # Maximum retries for failed orders
    RETRY_DELAY_SECONDS = 2  # Base delay between retries (exponential backoff)
    
    # Monitoring configuration
    POSITION_CHECK_INTERVAL = 30  # Seconds between position validation
    WINDOW_CHECK_INTERVAL = 10  # Seconds between window state checks
    
    # Logging configuration
    LOG_LEVEL = "INFO"  # Default log level
    LOG_ORDERS = True  # Log all order operations
    LOG_PHASE_TRANSITIONS = True  # Log phase changes
    LOG_UNIT_CHANGES = True  # Log unit boundary crossings
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate configuration settings"""
        if cls.FRAGMENT_PERCENT * cls.NUM_FRAGMENTS != Decimal("1.0"):
            raise ValueError("Fragment percentages must sum to 100%")
        
        if cls.WINDOW_SIZE != cls.NUM_FRAGMENTS:
            raise ValueError("Window size must equal number of fragments")
        
        if cls.MIN_ORDER_SIZE_USD >= cls.MAX_POSITION_SIZE_USD:
            raise ValueError("Min order size must be less than max position size")
        
        return True


class TestnetConfig:
    """Configuration for testnet environment"""
    
    # API endpoints
    TESTNET_API_URL = "https://api.hyperliquid-testnet.xyz"
    TESTNET_WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"
    
    # Test position sizes
    TEST_POSITION_SIZE_USD = Decimal("1000")  # Smaller size for testing
    TEST_UNIT_SIZE_USD = Decimal("25")  # Unit size for testing
    
    # Test mode flags
    SIMULATE_ORDERS = False  # If True, don't place real orders
    LOG_VERBOSE = True  # Extra logging in test mode


class MainnetConfig:
    """Configuration for mainnet environment"""
    
    # API endpoints
    MAINNET_API_URL = "https://api.hyperliquid.xyz"
    MAINNET_WS_URL = "wss://api.hyperliquid.xyz/ws"
    
    # Safety limits
    MAX_DAILY_TRADES = 1000  # Maximum trades per day
    MAX_POSITION_CHANGE_PERCENT = Decimal("0.5")  # Max 50% position change per order
    
    # Emergency controls
    ENABLE_EMERGENCY_STOP = True  # Allow emergency position close
    EMERGENCY_STOP_LOSS_PERCENT = Decimal("0.2")  # 20% stop loss trigger