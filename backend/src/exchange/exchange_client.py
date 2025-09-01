"""
Native Hyperliquid Exchange Client - Complete Implementation
Replaces CCXT with direct Hyperliquid API integration
Based on official Hyperliquid Python SDK patterns
"""
import json
import time
import requests
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_account.messages import encode_defunct

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
        
        # This section for loading settings is kept as is
        try:
            from src.utils import settings
            private_key = settings.HYPERLIQUID_TESTNET_PRIVATE_KEY
            self.master_address = settings.hyperliquid_wallet_key
            
            if use_vault and hasattr(settings, 'HYPERLIQUID_TESTNET_SUB_WALLET_LONG'):
                self.wallet_address = settings.HYPERLIQUID_TESTNET_SUB_WALLET_LONG
                self.is_vault = True
                logger.info("Using sub-account (vault)")
            else:
                self.wallet_address = self.master_address
                self.is_vault = False
                logger.info("Using master account")
                
        except ImportError:
            import os
            private_key = os.getenv("HYPERLIQUID_TESTNET_PRIVATE_KEY")
            self.wallet_address = os.getenv("HYPERLIQUID_WALLET_KEY")
            self.master_address = self.wallet_address
            self.is_vault = False
        
        if not private_key:
            raise ValueError("Hyperliquid private key not configured")
        
        self.wallet: LocalAccount = Account.from_key(private_key)
        # Removed address logging for security
        
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        self._meta_cache = {}
        self._meta_cache_time = 0
        
        logger.info(f"Initialized Hyperliquid {'testnet' if testnet else 'mainnet'} client")
    
    # --- INTERNAL METHODS ---

    def _post_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise

    def _get_meta(self) -> Dict[str, Any]:
        current_time = time.time()
        if current_time - self._meta_cache_time < 30 and self._meta_cache:
            return self._meta_cache
        
        payload = {"type": "meta"}
        result = self._post_request("/info", payload)
        self._meta_cache = result
        self._meta_cache_time = current_time
        return result
    
    def _symbol_to_asset_id(self, symbol: str) -> int:
        base_currency = symbol.split("/")[0] if "/" in symbol else symbol
        meta = self._get_meta()
        universe = meta.get("universe", [])
        
        for i, asset in enumerate(universe):
            if asset.get("name") == base_currency:
                # Return the index as the asset ID
                return i
        
        raise ValueError(f"Asset {base_currency} not found in metadata universe")

    def _sign_and_build_payload(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        [CORRECTED] This function now correctly signs the action and builds the final payload.
        """
        nonce = int(time.time() * 1000)
        
        # The signature is derived from a hash of a tuple of the action items
        # This is a critical step that differs from simple message signing
        action_tuple = tuple(action.items())
        hash_obj = Account.sign_message(encode_defunct(text=str(action_tuple)), self.wallet.key)
        
        # The API expects r, s, v as separate components of the signature
        signature = {
            "r": "0x" + hash_obj.r.to_bytes(32, 'big').hex(),
            "s": "0x" + hash_obj.s.to_bytes(32, 'big').hex(),
            "v": hash_obj.v,
        }

        payload = {
            "action": action,
            "nonce": nonce,
            "signature": signature
        }

        # If trading on behalf of a sub-account/vault, add its address
        if self.is_vault:
             payload["vaultAddress"] = self.wallet_address

        return payload

    # --- PUBLIC API METHODS ---

    def get_balance(self, currency: str = "USDC") -> Balance:
        """Get account balance - replaces fetch_balance()"""
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address
        }
        result = self._post_request("/info", payload)
        
        # Using accountValue for total, and marginSummary for available/used calculation
        margin_summary = result.get("marginSummary", {})
        total_value = Decimal(str(margin_summary.get("accountValue", "0")))
        total_margin_used = Decimal(str(margin_summary.get("totalMarginUsed", "0")))
        
        return Balance(
            currency=currency,
            available=total_value - total_margin_used,
            total=total_value
        )

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol - replaces fetch_positions()"""
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address
        }
        result = self._post_request("/info", payload)
        
        asset_id = self._symbol_to_asset_id(symbol)
        
        for pos_data in result.get("assetPositions", []):
            if pos_data.get("position", {}).get("coin") == symbol.split("/")[0]:
                position_info = pos_data["position"]
                szi = Decimal(position_info["szi"])
                
                if szi.is_zero():
                    continue

                size = abs(szi)
                side = "long" if szi > 0 else "short"
                
                return Position(
                    symbol=symbol,
                    side=side,
                    size=size,
                    entry_price=Decimal(position_info["entryPx"]),
                    mark_price=self.get_current_price(symbol), # Fetches current price
                    unrealized_pnl=Decimal(pos_data["unrealizedPnl"]),
                    margin_used=Decimal(position_info["marginUsed"])
                )
        return None
    
    def get_current_price(self, symbol: str) -> Decimal:
        """Get current price - replaces fetch_ticker()"""
        base_currency = symbol.split("/")[0] if "/" in symbol else symbol
        payload = {"type": "allMids"}
        result = self._post_request("/info", payload)
        
        if base_currency in result:
            return Decimal(str(result[base_currency]))
        
        raise ValueError(f"Could not get price for {symbol}")

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
        asset_id = self._symbol_to_asset_id(symbol)
        
        is_buy = side.lower() == "buy"
        
        # For market orders, Hyperliquid requires a limit price far enough away to guarantee execution
        if order_type.lower() == "market":
            current_price = self.get_current_price(symbol)
            slippage_fraction = Decimal("0.05") # 5% slippage for safety
            if is_buy:
                price = current_price * (Decimal("1") + slippage_fraction)
            else:
                price = current_price * (Decimal("1") - slippage_fraction)
            order_type_payload = {"market": {}}
        else:
            if price is None:
                raise ValueError("Price is required for limit orders")
            order_type_payload = {"limit": {"tif": "Gtc"}}

        # [CORRECTED] Payload structure must match API docs exactly
        action = {
            "type": "order",
            "orders": [
                {
                    "asset": asset_id,
                    "isBuy": is_buy,
                    "reduceOnly": reduce_only,
                    "limitPx": f"{price:.2f}", # Price as a string with 2 decimal places
                    "sz": str(size),
                    "orderType": order_type_payload,
                }
            ],
            "grouping": "na"
        }
        
        payload = self._sign_and_build_payload(action)
        logger.debug(f"Sending order payload: {json.dumps(payload, indent=2)}")
        result = self._post_request("/exchange", payload)
        
        if result.get("status") == "ok":
            status_data = result['data']
            if status_data['type'] == 'order':
                status = status_data['statuses'][0]
                if "filled" in status:
                    filled = status['filled']
                    return OrderResult(
                        id=str(filled['oid']),
                        status='filled',
                        price=Decimal(filled['avgPx']),
                        coin_amount=Decimal(filled['totalSz']),
                        info=result
                    )
                elif "resting" in status:
                    return OrderResult(
                        id=str(status['resting']['oid']),
                        status='open',
                        price=price,
                        info=result
                    )
        
        return OrderResult(status="rejected", info=result)
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a specific asset."""
        try:
            asset_id = self._symbol_to_asset_id(symbol)
            action = {
                "type": "updateLeverage",
                "asset": asset_id,
                "isCross": True, # Hyperliquid mainly uses cross margin
                "leverage": leverage
            }
            payload = self._sign_and_build_payload(action)
            result = self._post_request("/exchange", payload)
            
            if result.get("status") == "ok":
                logger.info(f"Set leverage to {leverage}x for {symbol}")
                return True
            else:
                logger.error(f"Failed to set leverage: {result}")
                return False

        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    def close_position(self, symbol: str) -> Optional[OrderResult]:
        """Close entire position for a given symbol."""
        position = self.get_position(symbol)
        if not position:
            logger.info(f"No position to close for {symbol}")
            return None

        close_side = "sell" if position.side == "long" else "buy"
        logger.info(f"Closing {position.side} position: {position.size} {symbol} by placing a {close_side} order.")
        
        return self.place_order(
            symbol=symbol,
            side=close_side,
            size=position.size,
            order_type="market",
            reduce_only=True
        )

    # --- STRATEGY-SPECIFIC METHODS ---

    async def buy_long_usd(
        self, 
        symbol: str, 
        usd_amount: Decimal, 
        leverage: Optional[int] = None
    ) -> OrderResult:
        if leverage:
            await self.set_leverage(symbol, leverage)
        
        current_price = self.get_current_price(symbol)
        coin_size = (usd_amount * Decimal(leverage)) / current_price
        
        coin_name = symbol.split("/")[0]
        logger.info(f"🟢 BUYING LONG: ${usd_amount} ({leverage}x) → {coin_size:.6f} {coin_name} @ ${current_price}")
        
        result = self.place_order(symbol, "buy", coin_size, "market")
        result.usd_amount = usd_amount
        result.leverage = leverage
        return result

    async def open_short_usd(
        self, 
        symbol: str, 
        usd_amount: Decimal, 
        leverage: Optional[int] = None
    ) -> OrderResult:
        if leverage:
            await self.set_leverage(symbol, leverage)
        
        current_price = self.get_current_price(symbol)
        coin_size = (usd_amount * Decimal(leverage)) / current_price

        coin_name = symbol.split("/")[0]
        logger.info(f"🔴 OPENING SHORT: ${usd_amount} ({leverage}x) → {coin_size:.6f} {coin_name} @ ${current_price}")

        result = self.place_order(symbol, "sell", coin_size, "market")
        result.usd_amount = usd_amount
        result.leverage = leverage
        return result

    async def sell_long_coin(
        self, 
        symbol: str, 
        coin_amount: Decimal, 
        reduce_only: bool = True
    ) -> OrderResult:
        current_price = self.get_current_price(symbol)
        usd_value = coin_amount * current_price
        coin_name = symbol.split("/")[0]
        logger.info(f"🟡 SELLING LONG: {coin_amount:.6f} {coin_name} → ${usd_value:.2f} @ ${current_price}")
        
        result = self.place_order(symbol, "sell", coin_amount, "market", reduce_only=reduce_only)
        result.usd_received = usd_value
        return result

    async def close_short_coin(
        self, 
        symbol: str, 
        coin_amount: Decimal
    ) -> OrderResult:
        current_price = self.get_current_price(symbol)
        usd_cost = coin_amount * current_price
        coin_name = symbol.split("/")[0]
        logger.info(f"🟢 CLOSING SHORT: {coin_amount:.6f} {coin_name} → ${usd_cost:.2f} @ ${current_price}")
        
        result = self.place_order(symbol, "buy", coin_amount, "market", reduce_only=True)
        result.usd_cost = usd_cost
        return result

# Backward compatibility alias
HyperliquidSDK = HyperliquidExchangeClient