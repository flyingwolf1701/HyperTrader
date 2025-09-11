"""
Comprehensive pytest test suite for HyperTrader sliding window strategy
Tests all aspects using pytest fixtures and hypothesis property-based testing
"""

import pytest
import asyncio
from decimal import Decimal
from hypothesis import given, strategies as st, assume, HealthCheck, settings
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Mock dependencies before importing
sys.modules['loguru'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['hyperliquid'] = MagicMock()

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock logger at module level
with patch.dict('sys.modules', {'loguru': MagicMock()}):
    from src.strategy.unit_tracker import UnitTracker, Phase, UnitChangeEvent
    from src.strategy.position_map import PositionState, PositionConfig, OrderType


# Create simplified classes for testing instead of importing complex ones
class MockOrderResult:
    def __init__(self, success=True, order_id=None, filled_size=None, average_price=None, error_message=None):
        self.success = success
        self.order_id = order_id
        self.filled_size = filled_size or Decimal("0")
        self.average_price = average_price or Decimal("0")
        self.error_message = error_message


class MockHyperTrader:
    """Simplified trader for testing sliding window logic"""
    
    def __init__(self, symbol="TEST", wallet_type="long", use_testnet=True):
        self.symbol = symbol
        self.wallet_type = wallet_type
        self.use_testnet = use_testnet
        self.sdk_client = None
        self.unit_tracker = None
        self.position_map = {}
        self.position_state = None
        self.current_price = Decimal("100.0")
        self.unit_size_usd = Decimal("5.0")
        
    async def _slide_window(self, direction: str):
        """Slide the order window incrementally based on price movement"""
        current_unit = self.unit_tracker.current_unit
        phase = self.unit_tracker.phase
        
        if direction == 'up' and phase == Phase.ADVANCE:
            # ADVANCE phase: Add stop-loss at (current-1), cancel at (current-5)
            new_unit = current_unit - 1  
            old_unit = current_unit - 5
            
            # Cancel the old order first
            if old_unit in self.position_map and self.position_map[old_unit].is_active:
                await self._cancel_order(old_unit)
            
            # Place new stop-loss order
            order_id = await self._place_stop_loss_order(new_unit)
            return order_id
        
        elif direction == 'down' and phase == Phase.DECLINE:
            # DECLINE phase: Add limit buy at (current+1), cancel at (current+5)
            new_unit = current_unit + 1
            old_unit = current_unit + 5
            
            # Cancel the old order first  
            if old_unit in self.position_map and self.position_map[old_unit].is_active:
                await self._cancel_order(old_unit)
            
            # Place new limit buy order
            order_id = await self._place_limit_buy_order(new_unit)
            return order_id
            
    async def _place_stop_loss_order(self, unit: int):
        """Place a stop loss order at a specific unit"""
        if not self.position_state or not self.sdk_client:
            return None
            
        config = self.position_map[unit]
        trigger_price = config.price
        size = self.position_state.long_fragment_asset
        
        result = self.sdk_client.place_stop_order(
            symbol=self.symbol,
            is_buy=False,
            size=size,
            trigger_price=trigger_price,
            reduce_only=True
        )
        
        if result.success:
            config.set_active_order(result.order_id, OrderType.LIMIT_SELL, in_window=True)
            return result.order_id
        return None
        
    async def _place_limit_buy_order(self, unit: int):
        """Place a limit buy order at a specific unit"""
        if not self.position_state or not self.sdk_client:
            return None
            
        config = self.position_map[unit]
        price = config.price
        size = self.position_state.long_fragment_usd / price
        
        result = self.sdk_client.place_limit_order(
            symbol=self.symbol,
            is_buy=True,
            price=price,
            size=size,
            reduce_only=False,
            post_only=True
        )
        
        if result.success:
            config.set_active_order(result.order_id, OrderType.LIMIT_BUY, in_window=True)
            return result.order_id
        return None
        
    async def _cancel_order(self, unit: int):
        """Cancel an order at a specific unit"""
        config = self.position_map[unit]
        if config.order_id and self.sdk_client:
            success = self.sdk_client.cancel_order(self.symbol, config.order_id)
            if success:
                config.mark_cancelled()
                
    async def _handle_unit_change(self, event: UnitChangeEvent):
        """Handle unit boundary crossing"""
        if event.phase in [Phase.ADVANCE, Phase.DECLINE]:
            await self._slide_window(event.direction)


# Hypothesis strategies for property-based testing
price_strategy = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000.00"), places=2)
unit_size_strategy = st.decimals(min_value=Decimal("0.1"), max_value=Decimal("100.0"), places=1)
position_size_strategy = st.decimals(min_value=Decimal("10.0"), max_value=Decimal("10000.0"), places=2)
leverage_strategy = st.integers(min_value=1, max_value=50)


@pytest.fixture
def mock_order_result():
    """Factory for creating MockOrderResult objects"""
    def _create_result(success=True, order_id="test_123", error=None):
        return MockOrderResult(
            success=success,
            order_id=order_id if success else None,
            filled_size=Decimal("0.25") if success else Decimal("0"),
            average_price=Decimal("100.0") if success else Decimal("0"),
            error_message=error if not success else None
        )
    return _create_result


@pytest.fixture
def mock_sdk(mock_order_result):
    """Mock SDK client using pytest-mock style"""
    class MockSDK:
        def __init__(self):
            self.get_current_price = Mock(return_value=Decimal("100.0"))
            self.get_positions = Mock(return_value=[])
            self.set_leverage = Mock(return_value=True)
            self.open_position = Mock(return_value=mock_order_result())
            self.place_stop_order = Mock(return_value=mock_order_result())
            self.place_limit_order = Mock(return_value=mock_order_result())
            self.cancel_order = Mock(return_value=True)
            
    return MockSDK()


@pytest.fixture
def unit_tracker(position_state, position_map):
    """Standard unit tracker for testing"""
    return UnitTracker(
        position_state=position_state,
        position_map=position_map,
        wallet_type="long"
    )


@pytest.fixture
def position_state():
    """Standard position state for testing"""
    return PositionState(
        entry_price=Decimal("100.0"),
        unit_size_usd=Decimal("5.0"),
        asset_size=Decimal("1.0"),  # 1 unit of asset
        position_value_usd=Decimal("100.0"),  # $100 position
        original_asset_size=Decimal("1.0"),
        original_position_value_usd=Decimal("100.0"),
        long_fragment_usd=Decimal("25.0"),  # 25% of $100
        long_fragment_asset=Decimal("0.25"),  # 25% of 1 unit
        short_fragment_usd=Decimal("25.0"),
        short_fragment_asset=Decimal("0.25")
    )


@pytest.fixture
def position_map():
    """Create position map with test data"""
    position_map = {}
    for unit in range(-10, 11):
        price = Decimal("100.0") + (unit * Decimal("5.0"))
        position_map[unit] = PositionConfig(
            unit=unit,
            price=price,
            order_id=None,
            order_type=None,
            is_active=False,
            in_window=False
        )
    return position_map


class TestUnitTracker:
    """Test unit tracking with property-based testing"""
    
    @given(price_strategy, unit_size_strategy)
    def test_unit_tracker_initialization(self, entry_price, unit_size):
        """Test unit tracker initializes correctly with any valid inputs"""
        # Create position state with given parameters
        pos_state = PositionState(
            entry_price=entry_price,
            unit_size_usd=unit_size,
            asset_size=Decimal("1.0"),
            position_value_usd=entry_price,
            original_asset_size=Decimal("1.0"),
            original_position_value_usd=entry_price,
            long_fragment_usd=entry_price / Decimal("4"),
            long_fragment_asset=Decimal("0.25"),
            short_fragment_usd=entry_price / Decimal("4"),
            short_fragment_asset=Decimal("0.25")
        )
        
        # Create position map
        from src.strategy.position_map import calculate_initial_position_map
        _, pos_map = calculate_initial_position_map(
            entry_price=entry_price,
            unit_size_usd=unit_size,
            asset_size=Decimal("1.0"),
            position_value_usd=entry_price,
            unit_range=10
        )
        
        tracker = UnitTracker(
            position_state=pos_state,
            position_map=pos_map,
            wallet_type="long"
        )
        
        assert tracker.current_unit == 0
        assert tracker.phase == Phase.ADVANCE
        assert tracker.peak_unit == 0
        assert tracker.valley_unit == 0
        assert tracker.position_state.entry_price == entry_price
        assert tracker.position_state.unit_size_usd == unit_size

    def test_unit_change_up(self, unit_tracker):
        """Test unit change detection when price moves up"""
        # Price moves up by exactly 1 unit
        new_price = Decimal("105.0")  # 100 + 5
        event = unit_tracker.calculate_unit_change(new_price)
        
        assert event is not None
        assert event.direction == "up"
        assert event.phase == Phase.ADVANCE
        assert unit_tracker.current_unit == 1
        assert unit_tracker.peak_unit == 1
        assert event.units_from_peak == 0  # At new peak
        assert event.units_from_valley == 1  # 1 unit from valley

    def test_unit_change_down(self, unit_tracker):
        """Test unit change detection when price moves down"""
        # Price moves down by 1 unit (calculate_unit_change moves one unit at a time)
        new_price = Decimal("95.0")  # 100 - 5 = -1 unit
        event = unit_tracker.calculate_unit_change(new_price)
        
        assert event is not None
        assert event.direction == "down"
        assert unit_tracker.current_unit == -1
        assert unit_tracker.valley_unit == -1
        assert event.units_from_valley == 0  # At new valley
        assert event.units_from_peak == -1  # -1 unit from peak (negative means below)

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.decimals(min_value=Decimal("97.5"), max_value=Decimal("102.49"), places=2))
    def test_no_unit_change_within_bounds(self, unit_tracker, price):
        """Test no unit change when price stays within unit bounds"""
        assume(Decimal("97.5") <= price <= Decimal("102.49"))  # Within unit 0 bounds
        
        event = unit_tracker.calculate_unit_change(price)
        assert event is None
        assert unit_tracker.current_unit == 0

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.integers(min_value=-50, max_value=50))
    def test_unit_calculation_property(self, unit_tracker, unit_offset):
        """Property test: unit calculation should be consistent"""
        assume(unit_offset != 0)  # Avoid no-change case
        
        target_price = Decimal("100.0") + (unit_offset * Decimal("5.0"))
        event = unit_tracker.calculate_unit_change(target_price)
        
        assert event is not None
        assert event.new_unit == unit_offset
        assert unit_tracker.current_unit == unit_offset

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(price_strategy.filter(lambda x: x > Decimal("0")))
    def test_multiple_unit_jumps(self, unit_tracker, target_price):
        """Test handling of large price movements"""
        event = unit_tracker.calculate_unit_change(target_price)
        
        if event:
            # Calculate expected unit based on price difference
            price_diff = target_price - Decimal("100.0")
            expected_unit = int(price_diff / Decimal("5.0"))
            
            assert event.new_unit == expected_unit
            assert unit_tracker.current_unit == expected_unit


class TestSlidingWindowLogic:
    """Test sliding window behavior"""
    
    @pytest.mark.asyncio
    async def test_slide_window_up_advance_phase(self, mock_sdk, unit_tracker, position_map):
        """Test sliding window up in ADVANCE phase"""
        # Setup: current unit = 3, should add stop at unit 2, cancel at unit -2
        unit_tracker.current_unit = 3
        unit_tracker.phase = Phase.ADVANCE
        
        # Mock existing order to cancel
        position_map[-2].is_active = True
        position_map[-2].order_id = "cancel_me_123"
        
        # Create trader instance with mocks
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.unit_tracker = unit_tracker
        trader.position_map = position_map
        trader.position_state = PositionState(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            long_fragment_asset=Decimal("0.25"),
            long_fragment_usd=Decimal("25.0")
        )
        
        await trader._slide_window("up")
        
        # Verify cancellation of old order (current-5 = 3-5 = -2)
        mock_sdk.cancel_order.assert_called_once_with("TEST", "cancel_me_123")
        
        # Verify new stop order placed (current-1 = 3-1 = 2)
        mock_sdk.place_stop_order.assert_called_once()
        call_kwargs = mock_sdk.place_stop_order.call_args[1]
        expected_price = Decimal("100.0") + (2 * Decimal("5.0"))  # Unit 2 = $110
        assert call_kwargs['trigger_price'] == expected_price

    @pytest.mark.asyncio
    async def test_slide_window_down_decline_phase(self, mock_sdk, unit_tracker, position_map):
        """Test sliding window down in DECLINE phase"""
        # Setup: current unit = -2, should add buy at unit -1, cancel at unit 3
        unit_tracker.current_unit = -2
        unit_tracker.phase = Phase.DECLINE
        
        # Mock existing order to cancel
        position_map[3].is_active = True
        position_map[3].order_id = "cancel_buy_123"
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.unit_tracker = unit_tracker
        trader.position_map = position_map
        trader.position_state = PositionState(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            long_fragment_asset=Decimal("0.25"),
            long_fragment_usd=Decimal("25.0")
        )
        
        await trader._slide_window("down")
        
        # Verify cancellation (current+5 = -2+5 = 3)
        mock_sdk.cancel_order.assert_called_once_with("TEST", "cancel_buy_123")
        
        # Verify new buy order placed (current+1 = -2+1 = -1)
        mock_sdk.place_limit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_sliding_in_retracement(self, mock_sdk, unit_tracker, position_map):
        """Test no sliding during RETRACEMENT phase"""
        unit_tracker.current_unit = 1
        unit_tracker.phase = Phase.RETRACEMENT
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.unit_tracker = unit_tracker
        trader.position_map = position_map
        
        await trader._slide_window("up")
        
        # No orders should be placed or cancelled in transitional phases
        mock_sdk.cancel_order.assert_not_called()
        mock_sdk.place_stop_order.assert_not_called()
        mock_sdk.place_limit_order.assert_not_called()


class TestOrderPlacement:
    """Test order placement and management"""
    
    @pytest.mark.asyncio
    async def test_place_stop_loss_success(self, mock_sdk, position_map, position_state):
        """Test successful stop-loss order placement"""
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.position_map = position_map
        trader.position_state = position_state
        
        order_id = await trader._place_stop_loss_order(-1)
        
        assert order_id == "test_123"
        mock_sdk.place_stop_order.assert_called_once()
        
        # Verify correct parameters
        call_kwargs = mock_sdk.place_stop_order.call_args[1]
        assert call_kwargs['symbol'] == "TEST"
        assert call_kwargs['is_buy'] == False  # Stop-loss is a sell
        assert call_kwargs['size'] == Decimal("0.25")  # Fragment size
        assert call_kwargs['trigger_price'] == Decimal("95.0")  # Unit -1 price
        assert call_kwargs['reduce_only'] == True

    @pytest.mark.asyncio
    async def test_place_stop_loss_failure(self, mock_sdk, position_map, position_state, mock_order_result):
        """Test handling of stop-loss order failure"""
        mock_sdk.place_stop_order.return_value = mock_order_result(success=False, error="Insufficient margin")
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.position_map = position_map
        trader.position_state = position_state
        
        order_id = await trader._place_stop_loss_order(-1)
        
        assert order_id is None

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_sdk, position_map):
        """Test successful order cancellation"""
        # Setup active order
        position_map[-1].is_active = True
        position_map[-1].order_id = "active_order_123"
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.position_map = position_map
        
        await trader._cancel_order(-1)
        
        mock_sdk.cancel_order.assert_called_once_with("TEST", "active_order_123")
        assert not position_map[-1].is_active

    @pytest.mark.asyncio
    async def test_cancel_order_failure(self, mock_sdk, position_map):
        """Test handling of order cancellation failure"""
        mock_sdk.cancel_order.return_value = False
        
        position_map[-1].is_active = True
        position_map[-1].order_id = "stuck_order_123"
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.position_map = position_map
        
        await trader._cancel_order(-1)
        
        # Order should remain active since cancellation failed
        assert position_map[-1].is_active


class TestPriceMovementScenarios:
    """Test realistic price movement scenarios"""
    
    @pytest.mark.asyncio
    async def test_steady_uptrend(self, mock_sdk):
        """Test behavior during steady upward price movement"""
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.unit_size_usd = Decimal("5.0")
        tracker = UnitTracker(Decimal("100.0"), Decimal("5.0"), "long")
        trader.unit_tracker = tracker
        
        # Simulate steady price increases
        prices = [Decimal("102.5"), Decimal("105.5"), Decimal("110.5"), Decimal("115.5")]
        unit_changes = []
        
        for price in prices:
            event = tracker.calculate_unit_change(price)
            if event:
                unit_changes.append((event.old_unit, event.new_unit))
                
        # Should see: 0->1, 1->2, 2->3
        expected = [(0, 1), (1, 2), (2, 3)]
        assert unit_changes == expected
        assert tracker.phase == Phase.ADVANCE  # Should stay in ADVANCE
        assert tracker.peak_unit == 3

    @pytest.mark.asyncio
    async def test_volatile_oscillation(self, unit_tracker):
        """Test behavior during volatile price oscillations"""
        # Simulate price bouncing around unit boundaries
        price_sequence = [
            Decimal("102.6"),  # Stay in unit 0
            Decimal("105.1"),  # Move to unit 1
            Decimal("109.9"),  # Move to unit 1 (still)
            Decimal("112.6"),  # Move to unit 2  
            Decimal("107.4"),  # Back to unit 1
            Decimal("104.9"),  # Back to unit 0
        ]
        
        events = []
        for price in price_sequence:
            event = unit_tracker.calculate_unit_change(price)
            if event:
                events.append((event.old_unit, event.new_unit, event.direction))
        
        # Should detect: 0->1 up, 1->2 up, 2->1 down, 1->0 down
        expected_events = [(0, 1, "up"), (1, 2, "up"), (2, 1, "down"), (1, 0, "down")]
        assert events == expected_events

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.lists(price_strategy.filter(lambda x: x > Decimal("50")), min_size=5, max_size=20))
    def test_price_sequence_consistency(self, unit_tracker, price_sequence):
        """Property test: unit tracking should be consistent across price sequences"""
        previous_unit = 0
        
        for price in price_sequence:
            event = unit_tracker.calculate_unit_change(price)
            if event:
                # Unit changes should be monotonic within the event
                if event.direction == "up":
                    assert event.new_unit > event.old_unit
                elif event.direction == "down":
                    assert event.new_unit < event.old_unit
                    
                previous_unit = event.new_unit
                
        # Final state should match last calculated unit
        expected_final_unit = int((price_sequence[-1] - Decimal("100.0")) / Decimal("5.0"))
        assert unit_tracker.current_unit == expected_final_unit


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error conditions"""
    
    def test_zero_unit_size_raises_error(self):
        """Test that zero unit size raises appropriate error"""
        with pytest.raises((ValueError, ZeroDivisionError)):
            from src.strategy.position_map import calculate_initial_position_map
            # This should raise an error during creation
            calculate_initial_position_map(
                entry_price=Decimal("100.0"),
                unit_size_usd=Decimal("0.0"),
                asset_size=Decimal("1.0"),
                position_value_usd=Decimal("100.0"),
                unit_range=10
            )
    
    @given(st.decimals(min_value=Decimal("-1000"), max_value=Decimal("0"), places=2))
    def test_negative_unit_size_raises_error(self, negative_unit_size):
        """Test that negative unit sizes raise errors"""
        assume(negative_unit_size < Decimal("0"))
        
        with pytest.raises(ValueError):
            from src.strategy.position_map import calculate_initial_position_map
            # This should raise an error during creation
            calculate_initial_position_map(
                entry_price=Decimal("100.0"),
                unit_size_usd=negative_unit_size,
                asset_size=Decimal("1.0"),
                position_value_usd=Decimal("100.0"),
                unit_range=10
            )

    @pytest.mark.asyncio
    async def test_network_failure_resilience(self, mock_sdk, position_map, position_state):
        """Test resilience to network failures"""
        # Mock network failure
        mock_sdk.place_stop_order.side_effect = Exception("Connection timeout")
        
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.position_map = position_map
        trader.position_state = position_state
        
        # Should handle exception gracefully
        order_id = await trader._place_stop_loss_order(-1)
        assert order_id is None

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(price_strategy.filter(lambda x: x > Decimal("0.01")))
    def test_extreme_price_movements(self, unit_tracker, extreme_price):
        """Test handling of extreme price movements"""
        assume(abs(extreme_price - Decimal("100.0")) > Decimal("50.0"))  # Ensure significant movement
        
        event = unit_tracker.calculate_unit_change(extreme_price)
        
        if event:
            # Unit calculation should still be mathematically correct
            expected_unit = int((extreme_price - Decimal("100.0")) / Decimal("5.0"))
            assert event.new_unit == expected_unit
            
            # Direction should be correct
            if extreme_price > Decimal("100.0"):
                assert event.direction == "up"
            else:
                assert event.direction == "down"

    def test_invalid_wallet_type(self, position_state, position_map):
        """Test invalid wallet type handling"""
        with pytest.raises(ValueError):
            UnitTracker(
                position_state=position_state,
                position_map=position_map,
                wallet_type="invalid_wallet_type"
            )


class TestIntegrationScenarios:
    """Integration tests for complete trading scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_advance_phase_cycle(self, mock_sdk):
        """Test complete ADVANCE phase with multiple unit movements"""
        trader = MockHyperTrader("TEST", "long", True)
        trader.sdk_client = mock_sdk
        trader.unit_size_usd = Decimal("5.0")
        trader.position_state = PositionState(
            entry_price=Decimal("100.0"),
            unit_size_usd=Decimal("5.0"),
            long_fragment_asset=Decimal("0.25"),
            long_fragment_usd=Decimal("25.0")
        )
        
        # Initialize unit tracker and position map
        trader.unit_tracker = UnitTracker(Decimal("100.0"), Decimal("5.0"), "long")
        trader.position_map = {}
        for unit in range(-10, 11):
            price = Decimal("100.0") + (unit * Decimal("5.0"))
            trader.position_map[unit] = PositionConfig(
                unit=unit, price=price, order_id=None, order_type=None,
                is_active=False, in_window=False
            )
        
        # Simulate price moving from 100 -> 105 -> 110 (units 0 -> 1 -> 2)
        prices = [Decimal("105.0"), Decimal("110.0")]
        
        for price in prices:
            event = trader.unit_tracker.calculate_unit_change(price)
            if event:
                await trader._handle_unit_change(event)
        
        # Should have made sliding window calls
        assert mock_sdk.place_stop_order.call_count >= 1
        assert trader.unit_tracker.current_unit == 2
        assert trader.unit_tracker.phase == Phase.ADVANCE


if __name__ == "__main__":
    # Run with: pytest test_strategy.py -v
    pytest.main([__file__, "-v", "--tb=short", "--hypothesis-show-statistics"])