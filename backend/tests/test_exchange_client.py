"""
Tests for Stage 3: CCXT Exchange Client
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from src.exchange_client import HyperliquidExchangeClient


class TestHyperliquidExchangeClient:
    """Test cases for HyperliquidExchangeClient"""
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_initialization(self, mock_settings, mock_ccxt):
        """Test exchange client initialization"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"ETH/USDC:USDC": {}}
        mock_ccxt.return_value = mock_exchange
        
        # Initialize client
        client = HyperliquidExchangeClient(testnet=True)
        
        # Verify initialization
        assert client.testnet is True
        assert client.exchange is not None
        mock_exchange.set_sandbox_mode.assert_called_once_with(True)
        mock_exchange.load_markets.assert_called_once()
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_get_balance(self, mock_settings, mock_ccxt):
        """Test fetching account balance"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {
            "USDC": {
                "free": 1000.0,
                "used": 100.0,
                "total": 1100.0
            }
        }
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        balance = client.get_balance("USDC")
        
        # Verify results
        assert balance["free"] == Decimal("1000.0")
        assert balance["used"] == Decimal("100.0")
        assert balance["total"] == Decimal("1100.0")
        mock_exchange.fetch_balance.assert_called_once()
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_get_balance_no_currency(self, mock_settings, mock_ccxt):
        """Test fetching balance for non-existent currency"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_balance.return_value = {}
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        balance = client.get_balance("BTC")
        
        # Should return zeros
        assert balance["free"] == Decimal("0")
        assert balance["used"] == Decimal("0")
        assert balance["total"] == Decimal("0")
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_get_position_active(self, mock_settings, mock_ccxt):
        """Test fetching active position"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_positions.return_value = [{
            "symbol": "ETH/USDC:USDC",
            "side": "long",
            "contracts": 0.5,
            "contractSize": 1,
            "percentage": 10.5,
            "unrealizedPnl": 50.0,
            "markPrice": 3500.0,
            "info": {"entryPx": "3450.0"}
        }]
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        position = client.get_position("ETH/USDC:USDC")
        
        # Verify results
        assert position is not None
        assert position["symbol"] == "ETH/USDC:USDC"
        assert position["side"] == "long"
        assert position["contracts"] == Decimal("0.5")
        assert position["entryPrice"] == Decimal("3450.0")
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_get_position_none(self, mock_settings, mock_ccxt):
        """Test fetching position when none exists"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {}
        mock_exchange.fetch_positions.return_value = [{
            "symbol": "ETH/USDC:USDC",
            "contracts": 0  # No position
        }]
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        position = client.get_position("ETH/USDC:USDC")
        
        # Should return None
        assert position is None
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_get_current_price(self, mock_settings, mock_ccxt):
        """Test fetching current market price"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {
            "ETH/USDC:USDC": {
                "info": {"midPx": "3500.50"}
            }
        }
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        price = client.get_current_price("ETH/USDC:USDC")
        
        # Verify result
        assert price == Decimal("3500.50")
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_place_market_order(self, mock_settings, mock_ccxt):
        """Test placing a market order"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {
            "ETH/USDC:USDC": {"info": {"midPx": "3500.00"}}
        }
        mock_exchange.amount_to_precision.return_value = "0.5"
        mock_exchange.price_to_precision.return_value = "3500.00"
        mock_exchange.create_order.return_value = {
            "id": "12345",
            "symbol": "ETH/USDC:USDC",
            "side": "buy",
            "amount": 0.5,
            "price": 3500.0,
            "status": "closed",
            "info": {}
        }
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        order = client.place_market_order(
            symbol="ETH/USDC:USDC",
            side="buy",
            amount=Decimal("0.5"),
            reduce_only=False
        )
        
        # Verify results
        assert order["id"] == "12345"
        assert order["symbol"] == "ETH/USDC:USDC"
        assert order["side"] == "buy"
        assert order["amount"] == Decimal("0.5")
        
        # Verify exchange was called correctly
        mock_exchange.create_order.assert_called_once_with(
            symbol="ETH/USDC:USDC",
            type="market",
            side="buy",
            amount=0.5,
            price=3500.0,
            params={"reduceOnly": False}
        )
    
    @patch('src.exchange_client.ccxt.hyperliquid')
    @patch('src.exchange_client.settings')
    def test_calculate_position_size(self, mock_settings, mock_ccxt):
        """Test position size calculation"""
        # Setup mocks
        mock_settings.hyperliquid_wallet_key = "0x123"
        mock_settings.hyperliquid_private_key = "0xabc"
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {}
        mock_ccxt.return_value = mock_exchange
        
        # Initialize and test
        client = HyperliquidExchangeClient()
        
        # Test calculation
        # Capital: $1000, Leverage: 10x, Price: $3500, Unit: 10%
        # Notional = 1000 * 0.10 * 10 = $1000
        # Contracts = 1000 / 3500 = 0.2857...
        size = client.calculate_position_size(
            capital=Decimal("1000"),
            leverage=10,
            current_price=Decimal("3500"),
            unit_percentage=Decimal("0.10")
        )
        
        expected = Decimal("1000") * Decimal("0.10") * 10 / Decimal("3500")
        assert size == expected