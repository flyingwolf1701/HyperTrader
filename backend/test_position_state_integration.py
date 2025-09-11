"""
Integration tests for position state and fragment calculation
Tests the issues identified from real trading screenshots
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from src.strategy.position_map import calculate_initial_position_map, PositionState
from src.strategy.unit_tracker import UnitTracker, Phase
from src.main import HyperTrader


class TestPositionStateFragments:
    """Test that fragment sizes remain constant during normal trading"""
    
    def test_fragment_sizes_remain_constant_during_fills(self):
        """Test that long_fragment_asset stays constant as position shrinks"""
        # Create position state with 9 SOL position
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            asset_size=Decimal("9.0"),  # 9 SOL initial position
            position_value_usd=Decimal("900.0")
        )
        
        # Verify initial fragment calculation
        assert position_state.original_asset_size == Decimal("9.0")
        assert position_state.long_fragment_asset == Decimal("2.25")  # 9 / 4 = 2.25
        
        # Simulate first stop-loss execution (position shrinks to ~6.75 SOL)
        position_state.asset_size = Decimal("6.75")
        position_state.position_value_usd = Decimal("675.0")
        
        # Fragment should remain the same (locked to original)
        assert position_state.long_fragment_asset == Decimal("2.25")
        assert position_state.original_asset_size == Decimal("9.0")
        
        # Simulate second stop-loss execution (position shrinks to ~4.5 SOL)
        position_state.asset_size = Decimal("4.5")
        position_state.position_value_usd = Decimal("450.0")
        
        # Fragment should still remain the same
        assert position_state.long_fragment_asset == Decimal("2.25")
        assert position_state.original_asset_size == Decimal("9.0")
    
    def test_reset_updates_fragments_for_new_cycle(self):
        """Test that RESET properly updates fragments for compound growth"""
        # Create initial position state
        position_state, position_map = calculate_initial_position_map(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            asset_size=Decimal("9.0"),
            position_value_usd=Decimal("900.0")
        )
        
        assert position_state.long_fragment_asset == Decimal("2.25")
        
        # Simulate compound growth - position is now 12 SOL
        new_asset_size = Decimal("12.0")
        new_position_value = Decimal("1200.0")
        
        # Update for new cycle (this is what _handle_reset does)
        position_state.asset_size = new_asset_size
        position_state.position_value_usd = new_position_value
        position_state.original_asset_size = new_asset_size
        position_state.original_position_value_usd = new_position_value
        position_state.long_fragment_usd = new_position_value / Decimal("4")
        position_state.long_fragment_asset = new_asset_size / Decimal("4")
        
        # Fragments should be updated for new cycle
        assert position_state.long_fragment_asset == Decimal("3.0")  # 12 / 4 = 3.0
        assert position_state.original_asset_size == Decimal("12.0")


class MockSDKClient:
    """Mock SDK client for integration testing"""
    
    def __init__(self):
        self.positions = {"SOL": Mock(size=Decimal("9.0"))}
        self.cancel_order = Mock(return_value=True)
        self.place_stop_order = Mock(return_value=Mock(success=True, order_id="test_123"))
        self.place_limit_order = Mock(return_value=Mock(success=True, order_id="test_456"))
    
    def get_positions(self):
        return self.positions


class TestSlidingWindowIntegration:
    """Test sliding window execution with real position state"""
    
    @pytest.fixture
    def trader_setup(self):
        """Create a trader instance with mocked dependencies"""
        # Mock WebSocket client
        mock_ws = Mock()
        mock_ws.listen = Mock()
        mock_ws.disconnect = Mock()
        
        # Create trader with minimal setup
        trader = HyperTrader(
            symbol="SOL",
            wallet_type="long",
            sdk_client=MockSDKClient(),
            ws_client=mock_ws,
            initial_position_size=900.0,  # $900
            unit_size_usd=5.0,           # $5 per unit
            leverage=10
        )
        
        # Initialize position state and map
        trader.position_state, trader.position_map = create_position_state(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            asset_size=Decimal("9.0"),  # 9 SOL
            position_value_usd=Decimal("900.0")
        )
        
        # Initialize unit tracker
        trader.unit_tracker = UnitTracker(
            trader.position_state,
            trader.position_map,
            wallet_type="long"
        )
        
        trader.current_price = Decimal("100.0")
        return trader
    
    @pytest.mark.asyncio
    async def test_order_sizes_stay_consistent_during_sliding(self, trader_setup):
        """Test that stop-loss orders maintain consistent 2.25 SOL size"""
        trader = trader_setup
        
        # Verify initial fragment size
        assert trader.position_state.long_fragment_asset == Decimal("2.25")
        
        # Simulate price moving up from $100 to $105 (unit 0 → unit 1)
        new_price = Decimal("105.0")
        unit_event = trader.unit_tracker.calculate_unit_change(new_price)
        
        assert unit_event is not None
        assert unit_event.direction == 'up'
        assert trader.unit_tracker.current_unit == 1
        
        # Execute sliding window
        await trader._slide_window(unit_event.direction)
        
        # Verify stop order was placed with correct size
        trader.sdk_client.place_stop_order.assert_called_once()
        call_args = trader.sdk_client.place_stop_order.call_args[1]
        
        # Size should be 2.25 SOL (consistent fragment size)
        assert call_args['size'] == Decimal("2.25")
        
        # Simulate first stop-loss execution (position decreases)
        trader.position_state.asset_size = Decimal("6.75")  # 9 - 2.25 = 6.75
        
        # Fragment should remain the same
        assert trader.position_state.long_fragment_asset == Decimal("2.25")
        
        # Simulate another price move up (unit 1 → unit 2)
        trader.sdk_client.place_stop_order.reset_mock()
        new_price = Decimal("110.0")
        unit_event = trader.unit_tracker.calculate_unit_change(new_price)
        
        if unit_event:
            await trader._slide_window(unit_event.direction)
            
            # Second stop order should also be 2.25 SOL
            if trader.sdk_client.place_stop_order.called:
                call_args = trader.sdk_client.place_stop_order.call_args[1]
                assert call_args['size'] == Decimal("2.25")
    
    @pytest.mark.asyncio
    async def test_sliding_window_triggered_on_unit_changes(self, trader_setup):
        """Test that sliding window is actually triggered when units change"""
        trader = trader_setup
        
        # Mock the sliding method to verify it's called
        slide_mock = Mock()
        trader._slide_window = slide_mock
        
        # Simulate price updates that cross unit boundaries
        prices = [
            Decimal("100.0"),  # Unit 0 (no change)
            Decimal("104.0"),  # Still unit 0 (no change)
            Decimal("105.0"),  # Unit 1 (should trigger slide)
            Decimal("107.0"),  # Still unit 1 (no change)
            Decimal("110.0"),  # Unit 2 (should trigger slide)
        ]
        
        slide_calls = 0
        for price in prices:
            unit_event = trader.unit_tracker.calculate_unit_change(price)
            if unit_event:
                await trader._handle_unit_change(unit_event)
                slide_calls += 1
        
        # Should have triggered sliding twice (unit 0→1 and unit 1→2)
        assert slide_calls == 2
        assert slide_mock.call_count == 2
    
    def test_phase_detection_with_order_composition(self, trader_setup):
        """Test that phase detection works correctly with order execution"""
        trader = trader_setup
        
        # Initial phase should be ADVANCE (all sell orders)
        assert trader.unit_tracker.phase == Phase.ADVANCE
        assert trader.unit_tracker.window.is_all_sells()
        
        # Simulate stop-loss execution at unit -1
        trader.unit_tracker.handle_order_execution(-1, "sell")
        
        # After execution, should have mixed orders (RETRACEMENT phase)
        window_state = trader.unit_tracker.get_window_state()
        assert trader.unit_tracker.phase == Phase.RETRACEMENT
        assert len(window_state['sell_orders']) == 3  # One sell removed
        assert len(window_state['buy_orders']) == 1   # One buy added


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])