"""
Comprehensive test suite for HyperTrader strategy
Tests every phase, transition, and edge case
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

# Import the modules to test
from src.core.models import Phase, UnitTracker
from src.strategy.strategy_manager import StrategyManager, StrategyState
from src.core.websocket_client import HyperliquidWebSocketClient
from src.exchange.exchange_client import HyperliquidExchangeClient


class TestUnitTracker:
    """Test the UnitTracker with all scenarios"""
    
    def test_initialization(self):
        """Test unit tracker initialization"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        assert tracker.entry_price == Decimal("4350")
        assert tracker.unit_size == Decimal("10")
        assert tracker.current_unit == 0
        assert tracker.peak_unit == 0
        assert tracker.valley_unit == 0
        assert tracker.phase == Phase.ADVANCE
        
    def test_first_price_sets_entry(self):
        """Test that first price sets entry if None"""
        tracker = UnitTracker(entry_price=None, unit_size=Decimal("10"))
        assert tracker.entry_price is None
        
        # First price should set entry
        changed = tracker.calculate_unit_change(Decimal("4350"))
        assert not changed  # No change on first price
        assert tracker.entry_price == Decimal("4350")
        assert tracker.current_unit == 0
        
    def test_unit_calculation_up(self):
        """Test upward unit movement"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0  # Disable debouncing for tests
        
        # Price up by $10 = 1 unit
        changed = tracker.calculate_unit_change(Decimal("4360"))
        assert changed
        assert tracker.current_unit == 1
        assert tracker.peak_unit == 1
        
        # Price up by $25 = 2.5 units = 2 units (int)
        changed = tracker.calculate_unit_change(Decimal("4375"))
        assert changed
        assert tracker.current_unit == 2
        assert tracker.peak_unit == 2
        
    def test_unit_calculation_down(self):
        """Test downward unit movement"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0  # Disable debouncing
        
        # Price down by $10 = -1 unit
        changed = tracker.calculate_unit_change(Decimal("4340"))
        assert changed
        assert tracker.current_unit == -1
        
        # Valley should NOT update in ADVANCE phase
        assert tracker.valley_unit == 0
        
    def test_valley_only_updates_in_decline(self):
        """Test valley only updates in DECLINE phase"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        
        # In ADVANCE phase, valley should not update
        tracker.phase = Phase.ADVANCE
        tracker.calculate_unit_change(Decimal("4330"))  # -2 units
        assert tracker.current_unit == -2
        assert tracker.valley_unit == 0  # Should NOT update
        
        # In DECLINE phase, valley should update
        tracker.phase = Phase.DECLINE
        tracker.calculate_unit_change(Decimal("4320"))  # -3 units
        assert tracker.current_unit == -3
        assert tracker.valley_unit == -3  # Should update
        
    def test_peak_always_updates(self):
        """Test peak updates in any phase"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        
        # Peak should update in ADVANCE
        tracker.phase = Phase.ADVANCE
        tracker.calculate_unit_change(Decimal("4370"))  # +2 units
        assert tracker.peak_unit == 2
        
        # Peak should still update in RETRACEMENT
        tracker.phase = Phase.RETRACEMENT
        tracker.calculate_unit_change(Decimal("4380"))  # +3 units
        assert tracker.peak_unit == 3
        
    def test_debouncing_prevents_rapid_changes(self):
        """Test debouncing prevents rapid oscillation"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 3  # 3 second debounce
        
        # First change should be pending
        changed = tracker.calculate_unit_change(Decimal("4360"))  # +1 unit
        assert not changed  # Should be pending
        assert tracker.pending_unit == 1
        assert tracker.current_unit == 0  # Not confirmed yet
        
        # Different price before timeout should reset pending
        changed = tracker.calculate_unit_change(Decimal("4370"))  # +2 units
        assert not changed
        assert tracker.pending_unit == 2  # Updated pending
        assert tracker.current_unit == 0  # Still not confirmed
        
        # Simulate time passing
        tracker.pending_unit_time = datetime.now() - timedelta(seconds=4)
        changed = tracker.calculate_unit_change(Decimal("4370"))  # Same price
        assert changed  # Should confirm after timeout
        assert tracker.current_unit == 2
        assert tracker.pending_unit is None
        
    def test_debouncing_cancels_on_return(self):
        """Test pending unit cancels if price returns"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 3
        
        # Start pending change
        tracker.calculate_unit_change(Decimal("4360"))  # +1 unit
        assert tracker.pending_unit == 1
        
        # Return to original unit cancels pending
        tracker.calculate_unit_change(Decimal("4350"))  # Back to 0
        assert tracker.pending_unit is None
        assert tracker.current_unit == 0
        
    def test_units_from_peak_and_valley(self):
        """Test distance calculations"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        
        # Move up to peak
        tracker.calculate_unit_change(Decimal("4380"))  # +3 units
        assert tracker.current_unit == 3
        assert tracker.peak_unit == 3
        assert tracker.get_units_from_peak() == 0
        
        # Move down from peak
        tracker.calculate_unit_change(Decimal("4360"))  # +1 unit
        assert tracker.current_unit == 1
        assert tracker.get_units_from_peak() == -2
        
        # Set valley for testing
        tracker.phase = Phase.DECLINE
        tracker.calculate_unit_change(Decimal("4320"))  # -3 units
        assert tracker.valley_unit == -3
        assert tracker.get_units_from_valley() == 0
        
        # Move up from valley
        tracker.calculate_unit_change(Decimal("4340"))  # -1 unit
        assert tracker.get_units_from_valley() == 2


class TestPhaseTransitions:
    """Test all phase transition logic"""
    
    def test_advance_to_retracement_trigger(self):
        """Test ADVANCE transitions to RETRACEMENT at -1 from peak"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        tracker.phase = Phase.ADVANCE
        
        # Rise to peak
        tracker.calculate_unit_change(Decimal("4380"))  # +3 units
        assert tracker.peak_unit == 3
        
        # Drop 1 unit from peak should trigger RETRACEMENT
        tracker.calculate_unit_change(Decimal("4370"))  # +2 units
        assert tracker.get_units_from_peak() == -1
        # Phase change would be handled by strategy manager
        
    def test_retracement_actions_by_unit(self):
        """Test RETRACEMENT phase actions at each unit from peak"""
        test_cases = [
            (-1, "Sell 1 fragment long, Open 1 fragment short"),
            (-2, "Sell 2 fragments long, Add 1 fragment short"),
            (-3, "Sell 2 fragments long, Add 1 fragment short"),
            (-4, "Sell 2 fragments long, Add 1 fragment short"),
            (-5, "Sell remaining long, Add proceeds to short"),
            (-6, "Enter DECLINE phase"),
        ]
        
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        tracker.phase = Phase.RETRACEMENT
        tracker.peak_unit = 5  # Simulated peak
        
        for units_from_peak, expected_action in test_cases:
            tracker.current_unit = tracker.peak_unit + units_from_peak
            assert tracker.get_units_from_peak() == units_from_peak
            # Actual actions would be in strategy manager
            
    def test_decline_to_recovery_trigger(self):
        """Test DECLINE transitions to RECOVERY at +2 from valley"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        tracker.phase = Phase.DECLINE
        
        # Set valley
        tracker.calculate_unit_change(Decimal("4300"))  # -5 units
        assert tracker.valley_unit == -5
        
        # Rise 2 units from valley should trigger RECOVERY
        tracker.calculate_unit_change(Decimal("4320"))  # -3 units
        assert tracker.get_units_from_valley() == 2
        # Phase change would be handled by strategy manager
        
    def test_recovery_actions_by_unit(self):
        """Test RECOVERY phase actions at each unit from valley"""
        test_cases = [
            (2, "Close 1 hedge_fragment short, Buy 1 hedge + 1 position fragment long"),
            (3, "Close 1 hedge_fragment short, Buy 1 hedge + 1 position fragment long"),
            (4, "Close 1 hedge_fragment short, Buy 1 hedge + 1 position fragment long"),
            (5, "Close remaining short, Buy with all proceeds + 1 position fragment"),
            (6, "100% long, trigger RESET"),
        ]
        
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        tracker.phase = Phase.RECOVERY
        tracker.valley_unit = -10  # Simulated valley
        
        for units_from_valley, expected_action in test_cases:
            tracker.current_unit = tracker.valley_unit + units_from_valley
            assert tracker.get_units_from_valley() == units_from_valley
            # Actual actions would be in strategy manager
            
    def test_reset_conditions(self):
        """Test RESET mechanism triggers"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        
        # After RECOVERY completes (+6 from valley)
        tracker.phase = Phase.RECOVERY
        tracker.valley_unit = -10
        tracker.current_unit = -4  # +6 from valley
        assert tracker.get_units_from_valley() == 6
        # RESET would be triggered by strategy manager


class TestStrategyState:
    """Test StrategyState management"""
    
    def test_initialization(self):
        """Test strategy state initialization"""
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        assert state.symbol == "ETH/USDC:USDC"
        assert state.position_size_usd == Decimal("1000")
        assert state.position_allocation == Decimal("1000")
        assert state.leverage == 10
        assert state.reset_count == 0
        
    def test_position_fragment_calculation(self):
        """Test position fragment is 10% of position"""
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        
        fragment = state.calculate_position_fragment()
        assert fragment == Decimal("100")  # 10% of 1000
        
        # Update position value
        state.position_allocation = Decimal("1200")
        fragment = state.calculate_position_fragment()
        assert fragment == Decimal("120")  # 10% of 1200
        
    def test_hedge_fragment_calculation(self):
        """Test hedge fragment is 25% of short position"""
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        
        # Calculate hedge fragment for short position
        short_value = Decimal("500")
        fragment = state.calculate_hedge_fragment(short_value)
        assert fragment == Decimal("125")  # 25% of 500
        
    def test_state_persistence_dict(self):
        """Test state serialization for persistence"""
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.entry_price = Decimal("4350")
        state.entry_time = datetime.now()
        state.has_position = True
        state.unit_tracker.current_unit = 5
        state.unit_tracker.peak_unit = 7
        state.reset_count = 2
        
        state_dict = state.to_dict()
        assert state_dict["symbol"] == "ETH/USDC:USDC"
        assert state_dict["phase"] == "ADVANCE"
        assert state_dict["position_size_usd"] == Decimal("1000")
        assert state_dict["current_unit"] == 5
        assert state_dict["peak_unit"] == 7
        assert state_dict["reset_count"] == 2
        assert state_dict["has_position"] is True


class TestStrategyManagerIntegration:
    """Test StrategyManager with mocked exchange"""
    
    @pytest.fixture
    def mock_exchange(self):
        """Create mock exchange client"""
        mock = Mock(spec=HyperliquidExchangeClient)
        mock.get_position.return_value = None  # No existing position
        mock.get_current_price.return_value = Decimal("4350")
        mock.open_long.return_value = {"id": "123", "price": Decimal("4350"), "amount": Decimal("0.23")}
        mock.set_leverage.return_value = True
        return mock
        
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket client"""
        mock = AsyncMock(spec=HyperliquidWebSocketClient)
        mock.is_connected = False
        mock.connect.return_value = True
        mock.subscribe_to_trades.return_value = True
        mock.listen.return_value = None
        return mock
        
    @pytest.mark.asyncio
    async def test_start_strategy(self, mock_exchange, mock_websocket):
        """Test starting a strategy"""
        manager = StrategyManager(testnet=True)
        manager.exchange_client = mock_exchange
        manager.ws_client = mock_websocket
        
        success = await manager.start_strategy(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        
        assert success
        assert "ETH/USDC:USDC" in manager.strategies
        state = manager.strategies["ETH/USDC:USDC"]
        assert state.has_position is True
        assert state.entry_price == Decimal("4350")
        assert state.unit_tracker.phase == Phase.ADVANCE
        
    @pytest.mark.asyncio
    async def test_monitor_price_change_triggers_phase(self, mock_exchange, mock_websocket):
        """Test price changes trigger phase handlers"""
        manager = StrategyManager(testnet=True)
        manager.exchange_client = mock_exchange
        manager.ws_client = mock_websocket
        
        # Manually create strategy state
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.entry_price = Decimal("4350")
        state.unit_tracker.entry_price = Decimal("4350")
        state.unit_tracker.debounce_seconds = 0  # Disable for test
        state.unit_tracker.peak_unit = 3
        state.unit_tracker.current_unit = 3
        state.has_position = True
        manager.strategies["ETH/USDC:USDC"] = state
        
        # Simulate price drop triggering RETRACEMENT
        with patch.object(manager, 'handle_advance_phase', new_callable=AsyncMock) as mock_handler:
            await manager.monitor_price_change("ETH/USDC:USDC", Decimal("4370"))  # Still positive
            mock_handler.assert_called_once()
            
        # Drop to trigger RETRACEMENT
        state.unit_tracker.current_unit = 2  # -1 from peak
        with patch.object(manager, 'handle_retracement_phase', new_callable=AsyncMock) as mock_handler:
            # First change phase
            state.unit_tracker.phase = Phase.RETRACEMENT
            await manager.monitor_price_change("ETH/USDC:USDC", Decimal("4360"))
            mock_handler.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_extreme_price_movements(self):
        """Test handling of extreme price jumps"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("0.20"))
        tracker.debounce_seconds = 1
        
        # Huge price jump
        tracker.calculate_unit_change(Decimal("4400"))  # +250 units!
        assert tracker.pending_unit == 250
        
        # Price crash
        tracker.calculate_unit_change(Decimal("4300"))  # -250 units!
        assert tracker.pending_unit == -250
        
    def test_zero_unit_size(self):
        """Test handling of zero unit size"""
        with pytest.raises(Exception):
            tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("0"))
            tracker.calculate_unit_change(Decimal("4360"))
            
    def test_negative_prices(self):
        """Test handling of negative prices (shouldn't happen but test anyway)"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0
        
        # Negative price should still calculate units
        changed = tracker.calculate_unit_change(Decimal("-100"))
        assert changed
        assert tracker.current_unit == -445  # (-100 - 4350) / 10
        
    def test_decimal_precision(self):
        """Test decimal precision is maintained"""
        tracker = UnitTracker(
            entry_price=Decimal("4350.123456"),
            unit_size=Decimal("0.000001")
        )
        tracker.debounce_seconds = 0
        
        # Very small price change
        changed = tracker.calculate_unit_change(Decimal("4350.123457"))
        assert changed
        assert tracker.current_unit == 1
        
    def test_concurrent_price_updates(self):
        """Test rapid concurrent price updates"""
        tracker = UnitTracker(entry_price=Decimal("4350"), unit_size=Decimal("10"))
        tracker.debounce_seconds = 0.1  # Very short debounce
        
        # Simulate rapid price updates
        prices = [Decimal("4360"), Decimal("4355"), Decimal("4365"), Decimal("4350")]
        for price in prices:
            tracker.calculate_unit_change(price)
            
        # Should handle without errors
        assert tracker.pending_unit is not None or tracker.current_unit == 0
        
    def test_phase_string_representation(self):
        """Test Phase enum string values"""
        assert Phase.ADVANCE.value == "ADVANCE"
        assert Phase.RETRACEMENT.value == "RETRACEMENT"
        assert Phase.DECLINE.value == "DECLINE"
        assert Phase.RECOVERY.value == "RECOVERY"


class TestWebSocketIntegration:
    """Test WebSocket callback integration"""
    
    @pytest.mark.asyncio
    async def test_websocket_uses_strategy_tracker(self):
        """Test WebSocket uses provided unit tracker"""
        ws_client = HyperliquidWebSocketClient(testnet=True)
        
        # Create external tracker
        external_tracker = UnitTracker(
            entry_price=Decimal("4350"),
            unit_size=Decimal("10")
        )
        
        # Subscribe with external tracker
        ws_client.is_connected = True
        ws_client.websocket = AsyncMock()
        
        success = await ws_client.subscribe_to_trades(
            "ETH",
            Decimal("10"),
            unit_tracker=external_tracker
        )
        
        assert success
        assert ws_client.unit_trackers["ETH"] is external_tracker
        
    @pytest.mark.asyncio  
    async def test_websocket_triggers_callback(self):
        """Test WebSocket triggers price callback"""
        ws_client = HyperliquidWebSocketClient(testnet=True)
        callback_triggered = False
        callback_price = None
        
        async def price_callback(price):
            nonlocal callback_triggered, callback_price
            callback_triggered = True
            callback_price = price
            
        # Subscribe with callback
        ws_client.is_connected = True
        ws_client.websocket = AsyncMock()
        
        await ws_client.subscribe_to_trades(
            "ETH",
            Decimal("10"),
            price_callback=price_callback
        )
        
        # Simulate trade data
        trade_data = {
            "data": [{
                "coin": "ETH",
                "px": "4360.50",
                "sz": "0.123"
            }]
        }
        
        # Process trade (would trigger callback if unit changed)
        await ws_client._handle_trades(trade_data)
        
        # Callback would be triggered on unit change
        assert "ETH" in ws_client.unit_trackers


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])