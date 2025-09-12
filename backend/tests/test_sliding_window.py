"""
Test sliding window implementation
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategy.unit_tracker import UnitTracker
from strategy.position_map import calculate_initial_position_map, add_unit_level
from strategy.data_models import Phase, PositionConfig, OrderType


class TestSlidingWindow:
    """Test the sliding window list-based tracking"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create position map
        self.entry_price = Decimal("4623.0")
        self.unit_size = Decimal("1.0")
        self.asset_size = Decimal("0.2163")
        self.position_value = Decimal("1000.0")
        
        self.position_state, self.position_map = calculate_initial_position_map(
            self.entry_price, self.unit_size, self.asset_size, self.position_value
        )
        
        # Create unit tracker
        self.unit_tracker = UnitTracker(self.position_state, self.position_map, "long")
        
    def test_initial_state(self):
        """Test initial window setup"""
        assert self.unit_tracker.trailing_stop == [-4, -3, -2, -1]
        assert self.unit_tracker.trailing_buy == []
        assert self.unit_tracker.current_unit == 0
        assert self.unit_tracker.phase == Phase.ADVANCE
        
    def test_add_remove_trailing_stop(self):
        """Test adding and removing stops from list"""
        # Add a new stop
        assert self.unit_tracker.add_trailing_stop(0) == True
        assert 0 in self.unit_tracker.trailing_stop
        assert self.unit_tracker.trailing_stop == [-4, -3, -2, -1, 0]
        
        # Try adding duplicate
        assert self.unit_tracker.add_trailing_stop(0) == False
        assert len([u for u in self.unit_tracker.trailing_stop if u == 0]) == 1
        
        # Remove a stop
        assert self.unit_tracker.remove_trailing_stop(-4) == True
        assert -4 not in self.unit_tracker.trailing_stop
        assert self.unit_tracker.trailing_stop == [-3, -2, -1, 0]
        
    def test_add_remove_trailing_buy(self):
        """Test adding and removing buys from list"""
        # Initially empty
        assert self.unit_tracker.trailing_buy == []
        
        # Add buys
        assert self.unit_tracker.add_trailing_buy(1) == True
        assert self.unit_tracker.add_trailing_buy(0) == True
        assert self.unit_tracker.trailing_buy == [0, 1]  # Should be sorted
        
        # Remove a buy
        assert self.unit_tracker.remove_trailing_buy(1) == True
        assert self.unit_tracker.trailing_buy == [0]
        
    def test_window_state_uses_lists(self):
        """Test that get_window_state uses the new lists"""
        state = self.unit_tracker.get_window_state()
        assert state['sell_orders'] == [-4, -3, -2, -1]
        assert state['buy_orders'] == []
        assert state['total_orders'] == 4
        
        # Add a buy and check
        self.unit_tracker.add_trailing_buy(1)
        state = self.unit_tracker.get_window_state()
        assert state['buy_orders'] == [1]
        assert state['total_orders'] == 5
        
    def test_unit_move_up_logic(self):
        """Test what happens when unit moves up from 0 to 1"""
        # Simulate unit moving up
        self.unit_tracker.current_unit = 1
        
        # What should happen:
        # 1. Add stop at current-1 = 0
        # 2. If > 4 stops, remove oldest (smallest)
        
        # Manually do what _slide_window_up should do
        new_stop = 0  # current_unit - 1
        self.unit_tracker.add_trailing_stop(new_stop)
        
        # Now we have 5 stops, remove oldest
        assert len(self.unit_tracker.trailing_stop) == 5
        assert self.unit_tracker.trailing_stop == [-4, -3, -2, -1, 0]
        
        old_stop = min(self.unit_tracker.trailing_stop)  # -4
        self.unit_tracker.remove_trailing_stop(old_stop)
        
        assert self.unit_tracker.trailing_stop == [-3, -2, -1, 0]
        assert len(self.unit_tracker.trailing_stop) == 4
        
    def test_unit_move_down_logic(self):
        """Test what happens when unit moves down from 0 to -1"""
        # Set current unit to -1
        self.unit_tracker.current_unit = -1
        
        # Check if stop at -1 exists (it should)
        assert -1 in self.unit_tracker.trailing_stop
        
        # Remove the triggered stop
        self.unit_tracker.remove_trailing_stop(-1)
        assert self.unit_tracker.trailing_stop == [-4, -3, -2]
        
        # Add replacement buy at current+1 = 0
        new_buy = 0  # current_unit + 1
        self.unit_tracker.add_trailing_buy(new_buy)
        
        assert self.unit_tracker.trailing_buy == [0]
        assert len(self.unit_tracker.trailing_stop) + len(self.unit_tracker.trailing_buy) == 4
        
    def test_multiple_moves_down(self):
        """Test multiple downward moves converting all stops to buys"""
        # Move from 0 to -1
        self.unit_tracker.current_unit = -1
        if -1 in self.unit_tracker.trailing_stop:
            self.unit_tracker.remove_trailing_stop(-1)
            self.unit_tracker.add_trailing_buy(0)
        
        # Move from -1 to -2  
        self.unit_tracker.current_unit = -2
        if -2 in self.unit_tracker.trailing_stop:
            self.unit_tracker.remove_trailing_stop(-2)
            self.unit_tracker.add_trailing_buy(-1)
            
        # Move from -2 to -3
        self.unit_tracker.current_unit = -3
        if -3 in self.unit_tracker.trailing_stop:
            self.unit_tracker.remove_trailing_stop(-3)
            self.unit_tracker.add_trailing_buy(-2)
            
        # Move from -3 to -4
        self.unit_tracker.current_unit = -4
        if -4 in self.unit_tracker.trailing_stop:
            self.unit_tracker.remove_trailing_stop(-4)
            self.unit_tracker.add_trailing_buy(-3)
        
        # Should have all buys now
        assert self.unit_tracker.trailing_stop == []
        assert self.unit_tracker.trailing_buy == [-3, -2, -1, 0]
        
    def test_deep_decline_window_management(self):
        """Test window management when going below initial range"""
        # Set up state where all stops converted to buys
        self.unit_tracker.trailing_stop = []
        self.unit_tracker.trailing_buy = [-3, -2, -1, 0]
        self.unit_tracker.current_unit = -4
        
        # Move to -5 (no stop to trigger, but maintain window)
        self.unit_tracker.current_unit = -5
        
        # Add new buy at current+1 = -4
        self.unit_tracker.add_trailing_buy(-4)
        
        # Should have 5 buys, need to remove oldest (highest value)
        assert len(self.unit_tracker.trailing_buy) == 5
        old_buy = max(self.unit_tracker.trailing_buy)  # Should be 0
        assert old_buy == 0
        
        self.unit_tracker.remove_trailing_buy(old_buy)
        assert self.unit_tracker.trailing_buy == [-4, -3, -2, -1]
        
    def test_price_calculations(self):
        """Test that position map prices are correct"""
        # Unit 0 should be at entry price
        assert self.position_map[0].price == self.entry_price
        
        # Unit 1 should be entry + 1 * unit_size
        assert self.position_map[1].price == self.entry_price + self.unit_size
        
        # Unit -1 should be entry - 1 * unit_size
        assert self.position_map[-1].price == self.entry_price - self.unit_size
        
        # Verify specific values
        assert self.position_map[1].price == Decimal("4624.0")
        assert self.position_map[-1].price == Decimal("4622.0")
        

class TestMainSlidingLogic:
    """Test the main.py sliding window functions"""
    
    @pytest.fixture
    def mock_trader(self):
        """Create a mock HyperTrader instance"""
        with patch('main.HyperliquidClient'), \
             patch('main.HyperliquidWebSocketClient'), \
             patch('main.load_dotenv'):
            
            # Import after patching
            from main import HyperTrader
            
            trader = HyperTrader("ETH", "long", True)
            trader.unit_size_usd = Decimal("1.0")
            trader.initial_position_size = Decimal("1000.0")
            trader.leverage = 10
            
            # Set up position map and unit tracker
            trader.position_state, trader.position_map = calculate_initial_position_map(
                Decimal("4623.0"), Decimal("1.0"), Decimal("0.2163"), Decimal("1000.0")
            )
            trader.unit_tracker = UnitTracker(trader.position_state, trader.position_map, "long")
            
            # Mock the order placement methods
            trader._place_stop_loss_order = AsyncMock(return_value="mock_order_id")
            trader._place_limit_buy_order = AsyncMock(return_value="mock_order_id")
            trader._cancel_order = AsyncMock(return_value=True)
            
            return trader
    
    @pytest.mark.asyncio
    async def test_slide_window_up(self, mock_trader):
        """Test _slide_window_up function"""
        trader = mock_trader
        
        # Mark the initial orders as active (simulating they were placed)
        for unit in [-4, -3, -2, -1]:
            trader.position_map[unit].is_active = True
            trader.position_map[unit].order_id = f"order_{unit}"
        
        # Set current unit to 1 (moved up from 0)
        trader.unit_tracker.current_unit = 1
        
        # Call slide window up
        await trader._slide_window_up()
        
        # Check that stop was added at 0 and old stop removed
        assert trader.unit_tracker.trailing_stop == [-3, -2, -1, 0]
        
        # Verify order placement was called
        trader._place_stop_loss_order.assert_called_once_with(0)
        
        # Verify cancellation was called for -4
        trader._cancel_order.assert_called_once_with(-4)
    
    @pytest.mark.asyncio
    async def test_slide_window_down_with_stop(self, mock_trader):
        """Test _slide_window_down when stop exists"""
        trader = mock_trader
        
        # Set current unit to -1 (moved down from 0)
        trader.unit_tracker.current_unit = -1
        
        # Verify -1 is in stops initially
        assert -1 in trader.unit_tracker.trailing_stop
        
        # Call slide window down
        await trader._slide_window_down()
        
        # Check that stop was removed and buy added
        assert -1 not in trader.unit_tracker.trailing_stop
        assert 0 in trader.unit_tracker.trailing_buy
        assert trader.unit_tracker.trailing_stop == [-4, -3, -2]
        assert trader.unit_tracker.trailing_buy == [0]
        
        # Verify buy order placement was called
        trader._place_limit_buy_order.assert_called_once_with(0)
    
    @pytest.mark.asyncio
    async def test_slide_window_down_no_stop(self, mock_trader):
        """Test _slide_window_down when no stop exists (initial move)"""
        trader = mock_trader
        
        # Remove -1 from stops to simulate it not existing
        trader.unit_tracker.trailing_stop = [-4, -3, -2]
        trader.unit_tracker.current_unit = -1
        
        # Call slide window down
        await trader._slide_window_down()
        
        # Should NOT add any buy since no stop was triggered
        assert trader.unit_tracker.trailing_buy == []
        
        # Verify no buy order was placed
        trader._place_limit_buy_order.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])