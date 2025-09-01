"""
Hyperliquid SDK Wrapper
Provides a clean interface to the Hyperliquid exchange
"""

from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from ..utils import settings


@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    is_long: bool
    size: Decimal
    entry_price: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    
    @property
    def side(self) -> str:
        return "LONG" if self.is_long else "SHORT"


@dataclass
class Balance:
    """Represents account balance"""
    total_value: Decimal
    margin_used: Decimal
    available: Decimal


@dataclass
class OrderResult:
    """Represents the result of an order"""
    success: bool
    order_id: Optional[str] = None
    filled_size: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    error_message: Optional[str] = None


class HyperliquidClient:
    """
    Main client for interacting with Hyperliquid exchange.
    Handles both main wallet and sub-wallet operations.
    """
    
    def __init__(self, use_testnet: bool = True, use_sub_wallet: bool = False):
        """
        Initialize the Hyperliquid client.
        
        Args:
            use_testnet: Whether to use testnet (True) or mainnet (False)
            use_sub_wallet: Whether to use sub-wallet for trading
        """
        self.use_testnet = use_testnet
        self.use_sub_wallet = use_sub_wallet
        
        # Set base URL based on network
        self.base_url = (
            "https://api.hyperliquid-testnet.xyz" if use_testnet 
            else "https://api.hyperliquid.xyz"
        )
        
        # Initialize wallet and clients
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize the SDK clients and wallet"""
        # Get credentials from environment variables
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        private_key = os.getenv("HYPERLIQUID_TESTNET_PRIVATE_KEY")
        self.main_wallet_address = os.getenv("HYPERLIQUID_WALLET_KEY")
        self.sub_wallet_address = os.getenv("HYPERLIQUID_TESTNET_SUB_WALLET_HEDGE")
        
        # Create wallet from private key (this is the agent/API key)
        self.wallet: LocalAccount = Account.from_key(private_key)
        
        # Initialize Info client for read operations
        self.info = Info(self.base_url, skip_ws=True)
        
        # Determine which wallet to use for trading
        if self.use_sub_wallet:
            # Trade on sub-wallet using vault_address
            self.trading_wallet_address = self.sub_wallet_address
            self.exchange = Exchange(
                wallet=self.wallet,
                base_url=self.base_url,
                vault_address=self.sub_wallet_address
            )
            logger.info(f"Initialized with sub-wallet {self.sub_wallet_address[:8]}...")
        else:
            # Trade on main wallet
            self.trading_wallet_address = self.main_wallet_address
            self.exchange = Exchange(
                wallet=self.wallet,
                base_url=self.base_url
            )
            logger.info(f"Initialized with main wallet {self.main_wallet_address[:8]}...")
    
    def switch_wallet(self, use_sub_wallet: bool):
        """
        Switch between main wallet and sub-wallet.
        
        Args:
            use_sub_wallet: True to use sub-wallet, False for main wallet
        """
        if use_sub_wallet != self.use_sub_wallet:
            self.use_sub_wallet = use_sub_wallet
            self._initialize_clients()
    
    # ============================================================================
    # ACCOUNT INFORMATION
    # ============================================================================
    
    def get_balance(self) -> Balance:
        """
        Get account balance for the current wallet.
        
        Returns:
            Balance object with total value, margin used, and available balance
        """
        try:
            user_state = self.info.user_state(self.trading_wallet_address)
            margin_summary = user_state.get("marginSummary", {})
            
            total_value = Decimal(str(margin_summary.get("accountValue", 0)))
            margin_used = Decimal(str(margin_summary.get("totalMarginUsed", 0)))
            
            return Balance(
                total_value=total_value,
                margin_used=margin_used,
                available=total_value - margin_used
            )
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            raise
    
    def get_positions(self) -> Dict[str, Position]:
        """
        Get all open positions for the current wallet.
        
        Returns:
            Dictionary mapping symbol to Position object
        """
        try:
            user_state = self.info.user_state(self.trading_wallet_address)
            positions = {}
            
            for asset_position in user_state.get("assetPositions", []):
                position_data = asset_position.get("position", {})
                szi = float(position_data.get("szi", 0))
                
                if szi != 0:  # Has an open position
                    symbol = position_data.get("coin")
                    positions[symbol] = Position(
                        symbol=symbol,
                        is_long=szi > 0,
                        size=Decimal(str(abs(szi))),
                        entry_price=Decimal(str(position_data.get("entryPx", 0))),
                        unrealized_pnl=Decimal(str(asset_position.get("unrealizedPnl", 0))),
                        margin_used=Decimal(str(position_data.get("marginUsed", 0)))
                    )
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            
        Returns:
            Position object if exists, None otherwise
        """
        positions = self.get_positions()
        return positions.get(symbol)
    
    # ============================================================================
    # MARKET DATA
    # ============================================================================
    
    def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            
        Returns:
            Current mid-market price
        """
        try:
            all_mids = self.info.all_mids()
            price = all_mids.get(symbol, 0)
            if price == 0:
                raise ValueError(f"Could not get price for {symbol}")
            return Decimal(str(price))
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            raise
    
    def get_market_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get market metadata for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Market information including decimals, leverage limits, etc.
        """
        try:
            meta = self.info.meta()
            for asset in meta.get("universe", []):
                if asset.get("name") == symbol:
                    return asset
            raise ValueError(f"Market info not found for {symbol}")
        except Exception as e:
            logger.error(f"Failed to get market info: {e}")
            raise
    
    # ============================================================================
    # TRADING OPERATIONS
    # ============================================================================
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading symbol
            leverage: Leverage multiplier (e.g., 10 for 10x)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.exchange.update_leverage(
                leverage=leverage,
                name=symbol,
                is_cross=True  # Use cross margin
            )
            if result.get("status") == "ok":
                logger.info(f"Set leverage to {leverage}x for {symbol}")
                return True
            else:
                logger.warning(f"Failed to set leverage: {result}")
                return False
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False
    
    def calculate_position_size(self, symbol: str, usd_amount: Decimal) -> Decimal:
        """
        Calculate position size in base currency from USD amount.
        
        Args:
            symbol: Trading symbol
            usd_amount: Position size in USD
            
        Returns:
            Position size in base currency, properly rounded
        """
        current_price = self.get_current_price(symbol)
        
        # Get market info for decimals
        market_info = self.get_market_info(symbol)
        sz_decimals = market_info.get("szDecimals", 4)
        
        # Calculate and round to appropriate decimals
        size = usd_amount / current_price
        return Decimal(str(round(float(size), sz_decimals)))
    
    def open_position(
        self, 
        symbol: str, 
        usd_amount: Decimal,
        is_long: bool = True,
        leverage: Optional[int] = None,
        slippage: float = 0.01
    ) -> OrderResult:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol (e.g., "ETH")
            usd_amount: Position size in USD
            is_long: True for long, False for short
            leverage: Optional leverage to set before opening
            slippage: Maximum slippage tolerance (default 1%)
            
        Returns:
            OrderResult with execution details
        """
        try:
            # Set leverage if specified
            if leverage:
                self.set_leverage(symbol, leverage)
            
            # Calculate position size
            position_size = self.calculate_position_size(symbol, usd_amount)
            
            logger.info(
                f"Opening {'LONG' if is_long else 'SHORT'} position: "
                f"{position_size} {symbol} (${usd_amount})"
            )
            
            # Place market order
            result = self.exchange.market_open(
                name=symbol,
                is_buy=is_long,
                sz=float(position_size),
                px=None,  # Let SDK calculate
                slippage=slippage
            )
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "filled" in statuses[0]:
                    filled = statuses[0]["filled"]
                    return OrderResult(
                        success=True,
                        order_id=str(filled.get("oid")),
                        filled_size=Decimal(str(filled.get("totalSz", 0))),
                        average_price=Decimal(str(filled.get("avgPx", 0)))
                    )
                elif statuses and "error" in statuses[0]:
                    return OrderResult(
                        success=False,
                        error_message=statuses[0]["error"]
                    )
            
            return OrderResult(
                success=False,
                error_message=f"Unexpected response: {result}"
            )
            
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def close_position(self, symbol: str, slippage: float = 0.01) -> OrderResult:
        """
        Close an existing position.
        
        Args:
            symbol: Trading symbol
            slippage: Maximum slippage tolerance
            
        Returns:
            OrderResult with execution details
        """
        try:
            # Get current position
            position = self.get_position(symbol)
            if not position:
                return OrderResult(
                    success=False,
                    error_message=f"No position to close for {symbol}"
                )
            
            logger.info(
                f"Closing {position.side} position: "
                f"{position.size} {symbol}"
            )
            
            # Close by opening opposite position
            # Note: market_close seems unreliable, using market_open instead
            result = self.exchange.market_open(
                name=symbol,
                is_buy=not position.is_long,  # Opposite side to close
                sz=float(position.size),
                px=None,
                slippage=slippage
            )
            
            # Parse result
            if result.get("status") == "ok":
                response = result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and "filled" in statuses[0]:
                    filled = statuses[0]["filled"]
                    return OrderResult(
                        success=True,
                        order_id=str(filled.get("oid")),
                        filled_size=Decimal(str(filled.get("totalSz", 0))),
                        average_price=Decimal(str(filled.get("avgPx", 0)))
                    )
            
            return OrderResult(
                success=False,
                error_message=f"Failed to close: {result}"
            )
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return OrderResult(
                success=False,
                error_message=str(e)
            )
    
    def close_all_positions(self) -> Dict[str, OrderResult]:
        """
        Close all open positions.
        
        Returns:
            Dictionary mapping symbol to OrderResult
        """
        results = {}
        positions = self.get_positions()
        
        for symbol, position in positions.items():
            logger.info(f"Closing {symbol} position...")
            results[symbol] = self.close_position(symbol)
        
        return results