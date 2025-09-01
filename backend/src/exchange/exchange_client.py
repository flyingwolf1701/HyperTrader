"""
Native Hyperliquid Exchange Client - Complete Implementation
Replaces CCXT with direct Hyperliquid API integration
Based on official Hyperliquid Python SDK patterns
"""
import json
import time
import hashlib
import requests
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from loguru import logger

import eth_account
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_account.messages import encode_typed_data, encode_defunct


# ============================================================================
# DATA TYPES (replaces ccxt_types.py)
# ============================================================================

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"

class TimeInForce(Enum):
    GTC = "Gtc"  # Good Till Canceled
    IOC = "Ioc"  # Immediate or Cancel
    ALO = "Alo"  # Add Liquidity Only (Post Only)


@dataclass
class Balance:
    """Account balance information"""
    currency: str
    available: Decimal
    total: Decimal
    
    @property
    def free(self) -> Decimal:
        return self.available
    
    @property
    def used(self) -> Decimal:
        return self.total - self.available


@dataclass
class Position:
    """Trading position information"""
    symbol: str
    side: str  # "long" or "short" 
    size: Decimal  # Position size in contracts
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    
    # Compatibility aliases for existing code
    @property
    def contracts(self) -> Decimal:
        return self.size
    
    @property
    def entryPrice(self) -> Decimal:
        return self.entry_price
    
    @property
    def unrealizedPnl(self) -> Decimal:
        return self.unrealized_pnl


@dataclass
class OrderResult:
    """Result of order execution"""
    id: str = ""
    type: str = ""
    price: Decimal = Decimal("0")
    coin_amount: Optional[Decimal] = None
    usd_amount: Optional[Decimal] = None
    usd_received: Optional[Decimal] = None
    usd_cost: Optional[Decimal] = None
    status: Optional[str] = None
    leverage: Optional[int] = None
    margin_used: Optional[Decimal] = None
    info: Optional[Dict] = None


# ============================================================================
# SIGNING UTILITIES (replaces signing.py)
# ============================================================================

def get_timestamp_ms() -> int:
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


def sign_l1_action(
    wallet: LocalAccount,
    action: Dict[str, Any],
    active_pool: Optional[str],
    nonce: int,
    expires_after: Optional[int],
    is_mainnet: bool = False
) -> str:
    """Sign L1 action using EIP-712"""
    
    # Build the action payload
    action_payload = {
        "action": action,
        "nonce": nonce
    }
    if expires_after:
        action_payload["expiresAfter"] = expires_after
    
    # Create signing message following Hyperliquid format
    action_string = json.dumps(action_payload, separators=(',', ':'))
    
    # Create the typed data following eth-account's expected format
    typed_data = {
        "domain": {
            "name": "HyperliquidSignTransaction",
            "version": "1", 
            "chainId": 42161,
            "verifyingContract": "0x0000000000000000000000000000000000000000"
        },
        "message": {
            "hyperliquidChain": "Mainnet" if is_mainnet else "Testnet",
            "signatureChainId": 42161,
            "action": action_string
        },
        "primaryType": "HyperliquidTransaction:UserAction",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"}
            ],
            "HyperliquidTransaction:UserAction": [
                {"name": "hyperliquidChain", "type": "string"},
                {"name": "signatureChainId", "type": "uint256"},
                {"name": "action", "type": "string"}
            ]
        }
    }
    
    try:
        # Try using encode_typed_data
        from eth_account.messages import encode_typed_data
        encoded_data = encode_typed_data(typed_data)
        signature = wallet.sign_message(encoded_data)
        return signature.signature.hex()
    except Exception as e:
        # Fallback to direct signing if EIP-712 fails
        logger.debug(f"EIP-712 signing failed: {e}, using direct signing")
        
        # Use direct message signing as fallback
        from eth_account.messages import encode_defunct
        message = encode_defunct(text=action_string)
        signature = wallet.sign_message(message)
        return signature.signature.hex()


# ============================================================================
# MAIN HYPERLIQUID CLIENT
# ============================================================================

class HyperliquidExchangeClient:
    """
    Native Hyperliquid Exchange Client
    Replaces CCXT implementation with direct API calls
    """
    
    def __init__(self, testnet: bool = True, use_vault: bool = False):
        """Initialize client from settings"""
        self.testnet = testnet
        self.base_url = (
            "https://api.hyperliquid-testnet.xyz" if testnet 
            else "https://api.hyperliquid.xyz"
        )
        
        # Get credentials from settings
        try:
            from src.utils import settings
            private_key = settings.HYPERLIQUID_TESTNET_PRIVATE_KEY
            
            # Store the master account address (which holds the funds)
            self.master_address = settings.hyperliquid_wallet_key
            
            # Check if we should use vault/sub-account
            if use_vault and hasattr(settings, 'HYPERLIQUID_TESTNET_SUB_WALLET_LONG'):
                # Use sub-account address for API calls
                self.wallet_address = settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG
                self.is_vault = True
                logger.info(f"Using sub-account (vault): {self.wallet_address}")
            else:
                # Use master account
                self.wallet_address = self.master_address
                self.is_vault = False
                logger.info(f"Using master account: {self.wallet_address}")
                
        except ImportError:
            # Fallback for standalone usage
            import os
            private_key = os.getenv("HYPERLIQUID_TESTNET_PRIVATE_KEY")
            self.wallet_address = os.getenv("HYPERLIQUID_WALLET_KEY")
            self.is_vault = False
        
        if not private_key:
            raise ValueError("Hyperliquid private key not configured")
        
        # Initialize wallet for signing (always use master account private key)
        self.wallet: LocalAccount = Account.from_key(private_key)
        logger.debug(f"Signer address: {self.wallet.address}")
        
        # Initialize HTTP session
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Cache for market data
        self._meta_cache = {}
        self._meta_cache_time = 0
        
        logger.info(f"Initialized Hyperliquid {'testnet' if testnet else 'mainnet'} client")
    
    def _post_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to Hyperliquid API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.post(url, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def _get_meta(self) -> Dict[str, Any]:
        """Get market metadata with caching"""
        current_time = time.time()
        
        # Cache for 30 seconds
        if current_time - self._meta_cache_time < 30 and self._meta_cache:
            return self._meta_cache
        
        payload = {"type": "meta"}
        result = self._post_request("/info", payload)
        
        self._meta_cache = result
        self._meta_cache_time = current_time
        
        return result
    
    def _symbol_to_asset_id(self, symbol: str) -> int:
        """Convert symbol to Hyperliquid asset ID"""
        base_currency = symbol.split("/")[0] if "/" in symbol else symbol
        
        meta = self._get_meta()
        universe = meta.get("universe", [])
        
        for i, asset in enumerate(universe):
            if asset.get("name") == base_currency:
                return i
        
        raise ValueError(f"Asset {base_currency} not found")
    
    # ========================================================================
    # ACCOUNT & POSITION METHODS (replaces CCXT methods)
    # ========================================================================
    
    def get_balance(self, currency: str = "USDC") -> Balance:
        """Get account balance - replaces fetch_balance()"""
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address
        }
        
        result = self._post_request("/info", payload)
        
        withdrawable = Decimal(str(result.get("withdrawable", "0")))
        margin_summary = result.get("marginSummary", {})
        total_margin_used = Decimal(str(margin_summary.get("totalMarginUsed", "0")))
        
        return Balance(
            currency=currency,
            available=withdrawable,
            total=withdrawable + total_margin_used
        )
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol - replaces fetch_positions()"""
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address
        }
        
        result = self._post_request("/info", payload)
        
        # Get asset info
        meta = self._get_meta()
        universe = meta.get("universe", [])
        
        asset_positions = result.get("assetPositions", [])
        
        for pos_data in asset_positions:
            position_info = pos_data.get("position", {})
            szi = position_info.get("szi", "0")
            
            if not szi or szi == "0":
                continue
            
            # Get asset info
            asset_idx = pos_data.get("assetIdx", 0)
            if asset_idx < len(universe):
                asset_name = universe[asset_idx].get("name", f"ASSET_{asset_idx}")
                pos_symbol = f"{asset_name}/USDC:USDC"
            else:
                pos_symbol = f"ASSET_{asset_idx}/USDC:USDC"
            
            # Check if this is the requested symbol
            if pos_symbol != symbol:
                continue
            
            # Extract position data
            size = Decimal(str(abs(float(szi))))
            side = "long" if float(szi) > 0 else "short"
            entry_price = Decimal(str(position_info.get("entryPx", "0")))
            unrealized_pnl = Decimal(str(position_info.get("unrealizedPnl", "0")))
            margin_used = Decimal(str(position_info.get("marginUsed", "0")))
            
            # Get current mark price
            mark_price = self.get_current_price(symbol)
            
            return Position(
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                mark_price=mark_price,
                unrealized_pnl=unrealized_pnl,
                margin_used=margin_used
            )
        
        return None
    
    def get_current_price(self, symbol: str) -> Decimal:
        """Get current price - replaces fetch_ticker()"""
        base_currency = symbol.split("/")[0] if "/" in symbol else symbol
        
        # Get prices from allMids endpoint
        payload = {"type": "allMids"}
        result = self._post_request("/info", payload)
        
        # Check if the currency is in the result
        if base_currency in result:
            price = result.get(base_currency)
            if price is not None:
                return Decimal(str(price))
        
        raise ValueError(f"Could not get price for {symbol}")
    
    # ========================================================================
    # ORDER EXECUTION METHODS (replaces CCXT create_order)
    # ========================================================================
    
    def place_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        order_type: str = "limit",
        price: Optional[Decimal] = None,
        reduce_only: bool = False
    ) -> OrderResult:
        """Place order - replaces create_order()"""
        
        # Get asset ID
        asset_id = self._symbol_to_asset_id(symbol)
        
        # Handle market orders
        if order_type.lower() == "market" and not price:
            current_price = self.get_current_price(symbol)
            buffer = current_price * Decimal("0.01")  # 1% buffer
            if side.lower() == "buy":
                price = current_price + buffer
            else:
                price = current_price - buffer
        
        if not price:
            raise ValueError("Price is required")
        
        # Create order wire
        order_wire = {
            "a": asset_id,
            "b": side.lower() == "buy",
            "p": str(price),
            "s": str(size),
            "r": reduce_only,
            "t": {
                "limit": {
                    "tif": "Ioc" if order_type.lower() == "market" else "Gtc"
                }
            }
        }
        
        # Sign the action
        nonce = get_timestamp_ms()
        action = {
            "type": "order",
            "orders": [order_wire]
        }
        
        # Include vault address if using sub-account
        if self.is_vault:
            action["vaultAddress"] = self.wallet_address
        
        signature = sign_l1_action(
            self.wallet,
            action,
            self.wallet_address if self.is_vault else None,
            nonce,
            None,
            not self.testnet
        )
        
        # Make request
        payload = {
            "action": action,
            "nonce": nonce,
            "signature": signature
        }
        
        # If signer is different from wallet, we're using an agent
        if self.wallet.address.lower() != self.wallet_address.lower():
            payload["vaultAddress"] = self.wallet_address
        
        logger.debug(f"Sending order payload: {json.dumps(payload, indent=2)}")
        result = self._post_request("/exchange", payload)
        
        # Parse response
        status_data = result.get("response", {}).get("data", {})
        statuses = status_data.get("statuses", [])
        
        if not statuses:
            return OrderResult(status="rejected", info=result)
        
        status = statuses[0]
        
        if "filled" in status:
            filled_data = status["filled"]
            return OrderResult(
                id=str(filled_data.get("oid", "")),
                type="filled",
                price=Decimal(str(filled_data.get("avgPx", "0"))),
                coin_amount=size,
                usd_amount=size * price if side.lower() == "buy" else None,
                usd_received=size * price if side.lower() == "sell" else None,
                status="filled",
                info=result
            )
        elif "resting" in status:
            return OrderResult(
                id=str(status["resting"].get("oid", "")),
                type="open",
                price=price,
                status="open",
                info=result
            )
        else:
            return OrderResult(status="rejected", info=result)
    
    # ========================================================================
    # STRATEGY-SPECIFIC METHODS (your USD buy/coin sell pattern)
    # ========================================================================
    
    async def buy_long_usd(
        self, 
        symbol: str, 
        usd_amount: Decimal, 
        leverage: Optional[int] = None
    ) -> OrderResult:
        """Buy long position using USD amount"""
        if leverage:
            self.set_leverage(symbol, leverage)
        
        current_price = self.get_current_price(symbol)
        coin_size = usd_amount / current_price
        
        # Extract coin name for logging
        coin_name = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info(f"🟢 BUYING LONG: ${usd_amount} → {coin_size:.6f} {coin_name} @ ${current_price}")
        
        result = self.place_order(
            symbol=symbol,
            side="buy",
            size=coin_size,
            order_type="market",
            reduce_only=False
        )
        
        # Add amounts to result
        result.usd_amount = usd_amount
        result.coin_amount = coin_size
        result.leverage = leverage
        result.margin_used = usd_amount / Decimal(leverage) if leverage else None
        
        return result
    
    async def open_short_usd(
        self, 
        symbol: str, 
        usd_amount: Decimal, 
        leverage: Optional[int] = None
    ) -> OrderResult:
        """Open short position using USD amount"""
        if leverage:
            self.set_leverage(symbol, leverage)
        
        current_price = self.get_current_price(symbol)
        coin_size = usd_amount / current_price
        
        # Extract coin name for logging
        coin_name = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info(f"🔴 OPENING SHORT: ${usd_amount} → {coin_size:.6f} {coin_name} @ ${current_price}")
        
        result = self.place_order(
            symbol=symbol,
            side="sell",
            size=coin_size,
            order_type="market",
            reduce_only=False
        )
        
        result.usd_amount = usd_amount
        result.coin_amount = coin_size
        result.leverage = leverage
        result.margin_used = usd_amount / Decimal(leverage) if leverage else None
        
        return result
    
    async def sell_long_coin(
        self, 
        symbol: str, 
        coin_amount: Decimal, 
        reduce_only: bool = True
    ) -> OrderResult:
        """Sell long position using coin amount"""
        current_price = self.get_current_price(symbol)
        usd_value = coin_amount * current_price
        
        # Extract coin name for logging
        coin_name = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info(f"🟡 SELLING LONG: {coin_amount:.6f} {coin_name} → ${usd_value:.2f} @ ${current_price}")
        
        result = self.place_order(
            symbol=symbol,
            side="sell", 
            size=coin_amount,
            order_type="market",
            reduce_only=reduce_only
        )
        
        result.coin_amount = coin_amount
        result.usd_received = usd_value
        
        return result
    
    async def close_short_coin(
        self, 
        symbol: str, 
        coin_amount: Decimal
    ) -> OrderResult:
        """Close short position using coin amount"""
        current_price = self.get_current_price(symbol)
        usd_cost = coin_amount * current_price
        
        # Extract coin name for logging
        coin_name = symbol.split("/")[0] if "/" in symbol else symbol
        
        logger.info(f"🟢 CLOSING SHORT: {coin_amount:.6f} {coin_name} → ${usd_cost:.2f} @ ${current_price}")
        
        result = self.place_order(
            symbol=symbol,
            side="buy",
            size=coin_amount,
            order_type="market",
            reduce_only=True
        )
        
        result.coin_amount = coin_amount
        result.usd_cost = usd_cost
        
        return result
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for symbol"""
        try:
            asset_id = self._symbol_to_asset_id(symbol)
            
            action = {
                "type": "updateLeverage",
                "asset": asset_id,
                "isCross": True,
                "leverage": leverage
            }
            
            # Include vault address if using sub-account
            if self.is_vault:
                action["vaultAddress"] = self.wallet_address
            
            nonce = get_timestamp_ms()
            signature = sign_l1_action(
                self.wallet,
                action,
                self.wallet_address if self.is_vault else None,
                nonce,
                None,
                not self.testnet
            )
            
            payload = {
                "action": action,
                "nonce": nonce,
                "signature": signature
            }
            
            result = self._post_request("/exchange", payload)
            logger.info(f"Set leverage {leverage}x for {symbol}")
            
            return "success" in result.get("status", "").lower()
            
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    def close_position(self, symbol: str) -> Optional[OrderResult]:
        """Close entire position"""
        position = self.get_position(symbol)
        
        if not position:
            logger.info(f"No position to close for {symbol}")
            return None
        
        # Determine close side
        close_side = "sell" if position.side == "long" else "buy"
        
        logger.info(f"Closing {position.side} position: {position.size} {symbol}")
        
        return self.place_order(
            symbol=symbol,
            side=close_side,
            size=position.size,
            order_type="market",
            reduce_only=True
        )


# Backward compatibility alias
HyperliquidSDK = HyperliquidExchangeClient
