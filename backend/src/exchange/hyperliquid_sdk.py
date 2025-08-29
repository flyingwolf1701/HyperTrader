import time
import requests
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_account.messages import encode_defunct
from eth_utils import keccak, to_bytes

class HyperliquidCustomSDK:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.hyperliquid-testnet.xyz"):
        self.base_url = base_url
        self.account: LocalAccount = Account.from_key(api_secret)
        self.wallet_address = self.account.address

    def _post(self, endpoint: str, payload: dict):
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as errh:
            print ("Http Error:",errh)
        except requests.exceptions.ConnectionError as errc:
            print ("Error Connecting:",errc)
        except requests.exceptions.Timeout as errt:
            print ("Timeout Error:",errt)
        except requests.exceptions.RequestException as err:
            print ("OOps: Something Else",err)
        return None

    def _sign_request(self, action: dict, vault_address: str = None):
        nonce = int(time.time() * 1000)
        connection_id = keccak(to_bytes(text=str(action)))
        
        signature = self.account.sign_message(
            encode_defunct(
                text=f"Hyperliquid REST API signature\n{self.wallet_address}\n{nonce}\n{connection_id.hex()}"
            )
        )

        return {
            "action": action,
            "nonce": nonce,
            "signature": signature.signature.hex(),
            "vaultAddress": vault_address,
        }

    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol format from ETH/USDC:USDC to ETH for Hyperliquid API"""
        if "/" in symbol:
            return symbol.split("/")[0]  # ETH from ETH/USDC:USDC
        return symbol

    def get_position(self, symbol: str):
        # Convert symbol format for Hyperliquid
        hl_symbol = self._convert_symbol(symbol)
        
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address,
        }
        response = self._post("info", payload)
        if response and "assetPositions" in response:
            for position in response["assetPositions"]:
                if position.get("position", {}).get("coin") == hl_symbol:
                    return {
                        "size": float(position["position"]["szi"]),
                        "entry_price": float(position["position"]["entryPx"]),
                        "side": "long" if float(position["position"]["szi"]) > 0 else "short",
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0)),
                    }
        return None

    def get_balance(self, currency: str = 'USDC'):
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address,
        }
        response = self._post("info", payload)
        if response:
            # Use accountValue from marginSummary
            if "marginSummary" in response and "accountValue" in response["marginSummary"]:
                return float(response["marginSummary"]["accountValue"])
            
            # Try withdrawable as fallback
            if "withdrawable" in response:
                return float(response["withdrawable"])
                
        return 0.0

    def get_current_price(self, symbol: str):
        from decimal import Decimal
        payload = {
            "type": "allMids"
        }
        response = self._post("info", payload)
        if response:
            return Decimal(str(response.get(symbol, 0)))
        return Decimal("0")

    def place_market_order(self, symbol: str, side: str, amount: float):
        # Convert symbol format for Hyperliquid
        hl_symbol = self._convert_symbol(symbol)
        
        action = {
            "type": "order",
            "orders": [
                {
                    "a": hl_symbol,
                    "b": side.lower() == "buy",
                    "p": "0",
                    "s": str(amount),
                    "r": False,
                    "t": {"market": {}},
                }
            ],
            "grouping": "na",
        }
        signed_payload = self._sign_request(action)
        return self._post("exchange", signed_payload)

    def close_position(self, symbol: str):
        position = self.get_position(symbol)
        if not position:
            return {"error": "No open position for this symbol."}

        side = "sell" if position["side"] == "long" else "buy"
        amount = abs(position["size"])
        
        return self.place_market_order(symbol, side, amount)

    async def buy_long_usd(self, symbol: str, usd_amount, leverage: int = 25):
        """Buy long position using USD amount - for simplified long-only strategy"""
        try:
            # Convert Decimal to float if needed
            usd_amount = float(usd_amount)
            
            print(f"[DEBUG] buy_long_usd: symbol={symbol}, usd_amount={usd_amount}, leverage={leverage}")
            
            current_price = self.get_current_price(symbol)
            print(f"[DEBUG] Current price: {current_price}")
            
            if current_price == 0:
                print("[DEBUG] Current price is 0, returning None")
                return None
                
            eth_amount = usd_amount / current_price
            print(f"[DEBUG] Calculated ETH amount: {eth_amount}")
            
            # Place market buy order
            result = self.place_market_order(symbol, "buy", eth_amount)
            print(f"[DEBUG] Market order result: {result}")
            
            if result:
                return {
                    "id": result.get("status", {}).get("resting", [{}])[0].get("oid", "") if result.get("status", {}).get("resting") else "",
                    "type": "buy_long_usd", 
                    "usd_amount": usd_amount,
                    "eth_amount": eth_amount,
                    "price": current_price,
                    "leverage": leverage,
                    "status": result.get("status"),
                    "info": result
                }
            return None
        except Exception as e:
            print(f"[DEBUG] Error in buy_long_usd: {e}")
            raise

    async def sell_long_eth(self, symbol: str, eth_amount, reduce_only: bool = True):
        """Sell long position using ETH amount - for retracement scaling"""
        # Convert Decimal to float if needed
        eth_amount = float(eth_amount)
        
        current_price = self.get_current_price(symbol)
        if current_price == 0:
            return None
            
        usd_value = eth_amount * current_price
        
        # Place market sell order
        result = self.place_market_order(symbol, "sell", eth_amount)
        
        if result:
            return {
                "id": result.get("status", {}).get("resting", [{}])[0].get("oid", "") if result.get("status", {}).get("resting") else "",
                "type": "sell_long_eth",
                "eth_amount": eth_amount,
                "usd_received": usd_value,
                "price": current_price,
                "reduce_only": reduce_only,
                "status": result.get("status"),
                "info": result
            }
        return None