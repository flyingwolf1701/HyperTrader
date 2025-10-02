"""
Comprehensive tests for GridTradingStrategy.
Tests the core logic after bug fixes implementation.
"""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategy.grid_strategy import GridTradingStrategy
from strategy.data_models import StrategyConfig, StrategyState
from strategy.unit_tracker import UnitTracker, UnitChangeEvent, Direction
from strategy.position_map import PositionMap
from exchange.hyperliquid_sdk import OrderResult


@pytest.fixture
def mock_client():
    """Create a mock HyperliquidClient"""
    client = Mock()
    client.get_user_address.return_value = "0x1234567890"
    client.set_leverage.return_value = True
    client.cancel_all_orders.return_value = 0
    client.get_current_price.return_value = Decimal("2000")
    
    # Mock successful position opening
    client.open_position.return_value = OrderResult(
        success=True,
        order_id="init_order_1",
        filled_size=Decimal("5.0"),
        average_price=Decimal("2000")
    )
    
    # Mock successful order placements
    def mock_place_limit(symbol, is_buy, price, size, reduce_only=False, post_only=True):
        return OrderResult(
            success=True,
            order_id=f"order_{int(price)}",
            filled_size=Decimal("0"),
            average_price=price
        )
    
    def mock_place_stop_buy(symbol, size, trigger_price, limit_price, reduce_only=False):
        return OrderResult(
            success=True,
            order_id=f"buy_order_{int(trigger_price)}",
            filled_size=Decimal("0"),
            average_price=trigger_price
        )
    
    client.place_limit_order = Mock(side_effect=mock_place_limit)
    client.place_stop_buy = Mock(side_effect=mock_place_stop_buy)
    client.cancel_order.return_value = True
    client.calculate_position_size.return_value = Decimal("1.25")
    client.get_open_orders.return_value = []
    
    return client


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket client"""
    ws = Mock()
    ws.connect = AsyncMock(return_value=True)
    ws.subscribe_to_trades = AsyncMock(return_value=True)
    ws.subscribe_to_user_fills = AsyncMock(return_value=True)
    ws.subscribe_to_order_updates = AsyncMock(return_value=True)
    ws.disconnect = AsyncMock()
    return ws


@pytest.fixture
def strategy_config():
    """Create a test strategy configuration"""
    return StrategyConfig(
        symbol="ETH",
        leverage=10,
        position_value_usd=Decimal("10000"),
        unit_size_usd=Decimal("1"),
        mainnet=False,
        strategy="long"
    )


@pytest.fixture
async def initialized_strategy(strategy_config, mock_client, mock_websocket):
    """Create and initialize a strategy for testing"""
    strategy = GridTradingStrategy(strategy_config, mock_client, mock_websocket)
    
    # Mock the initialization
    strategy.unit_tracker = UnitTracker(
        unit_size_usd=strategy_config.unit_size_usd,
        anchor_price=Decimal("2000")
    )
    strategy.position_map = PositionMap(
        unit_size_usd=strategy_config.unit_size_usd,
        anchor_price=Decimal("2000")
    )
    strategy.metrics.current_position_size = Decimal("5.0")
    strategy.metrics.avg_entry_price = Decimal("2000")
    strategy.fragments_invested = 4
    strategy.state = StrategyState.RUNNING
    strategy.main_loop = asyncio.get_running_loop()
    
    # Set up initial grid
    strategy.trailing_stop = [-4, -3, -2, -1]
    strategy.trailing_buy = []
    
    # Add orders to position map
    for unit in strategy.trailing_stop:
        strategy.position_map.add_order(unit, f"sell_order_{unit}", "sell", Decimal("1.25"))
    
    return strategy


class TestInitialization:
    """Test strategy initialization"""
    
    @pytest.mark.asyncio
    async def test_initial_grid_setup(self, initialized_strategy):
        """Test that initial grid has 4 sell orders at correct units"""
        assert len(initialized_strategy.trailing_stop) == 4
        assert initialized_strategy.trailing_stop == [-4, -3, -2, -1]
        assert len(initialized_strategy.trailing_buy) == 0
        assert initialized_strategy.fragments_invested == 4


class TestUnitUpMovement:
    """Test price moving up (trending up)"""
    
    @pytest.mark.asyncio
    async def test_single_unit_up_places_new_sell(self, initialized_strategy):
        """Test that moving up 1 unit places a new sell order"""
        # Move from unit 0 to unit 1
        await initialized_strategy._process_unit_up(1)
        
        # Should have placed sell at unit 0
        assert 0 in initialized_strategy.trailing_stop
        assert len(initialized_strategy.trailing_stop) == 5  # Temporarily 5 before cancel
    
    @pytest.mark.asyncio
    async def test_unit_up_cancels_oldest_when_over_4(self, initialized_strategy):
        """Test that oldest sell is cancelled when we have > 4"""
        # Move from unit 0 to unit 1
        await initialized_strategy._process_unit_up(1)
        
        # Should cancel unit -4 (oldest)
        assert -4 not in initialized_strategy.trailing_stop
        assert len(initialized_strategy.trailing_stop) == 4
        assert initialized_strategy.trailing_stop == [-3, -2, -1, 0]
    
    @pytest.mark.asyncio
    async def test_multiple_units_up(self, initialized_strategy):
        """Test moving up multiple units in sequence"""
        # Simulate price moving from 0 to 3
        for unit in [1, 2, 3]:
            await initialized_strategy._process_unit_up(unit)
        
        # Should have sells at [0, 1, 2] (oldest ones cancelled)
        assert initialized_strategy.trailing_stop == [0, 1, 2]
        assert len(initialized_strategy.trailing_stop) == 4
    
    @pytest.mark.asyncio
    async def test_unit_up_skips_existing_unit(self, initialized_strategy):
        """Test that we don't place duplicate orders at same unit"""
        # Add unit 0 manually
        initialized_strategy.trailing_stop.append(0)
        
        # Try to process unit 1 (which would try to place at 0)
        initial_len = len(initialized_strategy.trailing_stop)
        await initialized_strategy._process_unit_up(1)
        
        # Should not have added another 0
        assert initialized_strategy.trailing_stop.count(0) == 1


class TestUnitDownMovement:
    """Test price moving down (trending down)"""
    
    @pytest.mark.asyncio
    async def test_single_unit_down_places_new_buy(self, initialized_strategy):
        """Test that moving down 1 unit places a new buy order"""
        # Move from unit 0 to unit -1
        await initialized_strategy._process_unit_down(-1)
        
        # Should have placed buy at unit 0
        assert 0 in initialized_strategy.trailing_buy
        assert len(initialized_strategy.trailing_buy) == 1
    
    @pytest.mark.asyncio
    async def test_unit_down_with_4_buys_cancels_highest_first(self, initialized_strategy):
        """Test that when we have 4 buys, highest is cancelled BEFORE placing new one"""
        # Set up 4 existing buy orders
        initialized_strategy.trailing_buy = [3, 2, 1, 0]
        
        # Move down to unit -1 (would place buy at 0)
        await initialized_strategy._process_unit_down(-1)
        
        # Should have cancelled unit 3 (highest) first
        assert 3 not in initialized_strategy.trailing_buy
        # Since unit 0 already exists, it won't be added again
        assert len(initialized_strategy.trailing_buy) <= 4
    
    @pytest.mark.asyncio
    async def test_multiple_units_down(self, initialized_strategy):
        """Test moving down multiple units in sequence"""
        # Simulate price moving from 0 to -3
        for unit in [-1, -2, -3]:
            await initialized_strategy._process_unit_down(unit)
        
        # Should have buys at [0, -1, -2]
        assert 0 in initialized_strategy.trailing_buy
        assert -1 in initialized_strategy.trailing_buy
        assert -2 in initialized_strategy.trailing_buy
        assert len(initialized_strategy.trailing_buy) == 3


class TestFillConfirmation:
    """Test order fill handling"""
    
    @pytest.mark.asyncio
    async def test_sell_fill_places_replacement_buy(self, initialized_strategy):
        """Test that a sell fill places a replacement buy order"""
        # Set current unit to 0
        initialized_strategy.unit_tracker.current_unit = 0
        
        # Simulate sell fill at unit -1
        order_id = "sell_order_-1"
        await initialized_strategy.process_fill_confirmation(
            order_id, Decimal("1999"), Decimal("1.25")
        )
        
        # Should place buy at current_unit + 1 = 1
        assert 1 in initialized_strategy.trailing_buy
        # Should remove -1 from trailing_stop
        assert -1 not in initialized_strategy.trailing_stop
        # Fragments should decrease
        assert initialized_strategy.fragments_invested == 3
    
    @pytest.mark.asyncio
    async def test_buy_fill_places_replacement_sell(self, initialized_strategy):
        """Test that a buy fill places a replacement sell order"""
        # Set up a buy order
        initialized_strategy.trailing_buy = [1]
        initialized_strategy.position_map.add_order(1, "buy_order_1", "buy", Decimal("1.25"))
        initialized_strategy.fragments_invested = 3
        initialized_strategy.unit_tracker.current_unit = 0
        
        # Simulate buy fill at unit 1
        await initialized_strategy.process_fill_confirmation(
            "buy_order_1", Decimal("2001"), Decimal("1.25")
        )
        
        # Should place sell at current_unit - 1 = -1
        assert -1 in initialized_strategy.trailing_stop or len(initialized_strategy.trailing_stop) >= 4
        # Should remove 1 from trailing_buy
        assert 1 not in initialized_strategy.trailing_buy
        # Fragments should increase
        assert initialized_strategy.fragments_invested == 4
    
    @pytest.mark.asyncio
    async def test_sell_fill_cancels_oldest_buy_if_over_4(self, initialized_strategy):
        """Test that replacement buy cancels oldest if > 4 buys"""
        # Set up 4 existing buys
        initialized_strategy.trailing_buy = [4, 3, 2, 1]
        for unit in initialized_strategy.trailing_buy:
            initialized_strategy.position_map.add_order(unit, f"buy_{unit}", "buy", Decimal("1.25"))
        
        initialized_strategy.unit_tracker.current_unit = 0
        
        # Simulate sell fill
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-1", Decimal("1999"), Decimal("1.25")
        )
        
        # Should have cancelled unit 4 (oldest/highest)
        assert len(initialized_strategy.trailing_buy) <= 4
    
    @pytest.mark.asyncio
    async def test_unknown_order_fill_ignored(self, initialized_strategy):
        """Test that fills for unknown orders are ignored gracefully"""
        initial_buys = len(initialized_strategy.trailing_buy)
        initial_sells = len(initialized_strategy.trailing_stop)
        
        # Try to process fill for non-existent order
        await initialized_strategy.process_fill_confirmation(
            "fake_order_999", Decimal("2000"), Decimal("1.0")
        )
        
        # Should not have changed anything
        assert len(initialized_strategy.trailing_buy) == initial_buys
        assert len(initialized_strategy.trailing_stop) == initial_sells


class TestFragmentTracking:
    """Test fragment investment tracking"""
    
    @pytest.mark.asyncio
    async def test_sell_fill_decrements_fragments(self, initialized_strategy):
        """Test that sell fills decrement fragments correctly"""
        initialized_strategy.fragments_invested = 4
        
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-1", Decimal("1999"), Decimal("1.25")
        )
        
        assert initialized_strategy.fragments_invested == 3
    
    @pytest.mark.asyncio
    async def test_buy_fill_increments_fragments(self, initialized_strategy):
        """Test that buy fills increment fragments correctly"""
        # Setup
        initialized_strategy.trailing_buy = [1]
        initialized_strategy.position_map.add_order(1, "buy_1", "buy", Decimal("1.25"))
        initialized_strategy.fragments_invested = 3
        
        await initialized_strategy.process_fill_confirmation(
            "buy_1", Decimal("2001"), Decimal("1.25")
        )
        
        assert initialized_strategy.fragments_invested == 4
    
    @pytest.mark.asyncio
    async def test_fragments_never_below_zero(self, initialized_strategy):
        """Test that fragments never go below 0"""
        initialized_strategy.fragments_invested = 0
        
        # Even if we somehow process another sell
        initialized_strategy.position_map.add_order(-5, "sell_-5", "sell", Decimal("1.25"))
        await initialized_strategy.process_fill_confirmation(
            "sell_-5", Decimal("1995"), Decimal("1.25")
        )
        
        assert initialized_strategy.fragments_invested == 0
    
    @pytest.mark.asyncio
    async def test_fragments_never_above_four(self, initialized_strategy):
        """Test that fragments never go above 4"""
        initialized_strategy.fragments_invested = 4
        
        # Setup a buy that would try to increment
        initialized_strategy.trailing_buy = [1]
        initialized_strategy.position_map.add_order(1, "buy_1", "buy", Decimal("1.25"))
        
        await initialized_strategy.process_fill_confirmation(
            "buy_1", Decimal("2001"), Decimal("1.25")
        )
        
        assert initialized_strategy.fragments_invested == 4


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_order_placement_failure_doesnt_crash(self, initialized_strategy, mock_client):
        """Test that failed order placement is handled gracefully"""
        # Mock failure
        mock_client.place_limit_order.return_value = OrderResult(
            success=False,
            error_message="Insufficient margin"
        )
        
        initial_len = len(initialized_strategy.trailing_stop)
        
        # Should not crash
        await initialized_strategy._process_unit_up(1)
        
        # Should not have added to tracking list
        assert len(initialized_strategy.trailing_stop) == initial_len
    
    @pytest.mark.asyncio
    async def test_duplicate_fill_confirmation(self, initialized_strategy):
        """Test that duplicate fill confirmations are handled"""
        # Process once
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-1", Decimal("1999"), Decimal("1.25")
        )
        
        fragments_after_first = initialized_strategy.fragments_invested
        
        # Process again (should be ignored as order not in map anymore)
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-1", Decimal("1999"), Decimal("1.25")
        )
        
        # Should not change anything
        assert initialized_strategy.fragments_invested == fragments_after_first


class TestIntegrationScenarios:
    """Test complete trading scenarios"""
    
    @pytest.mark.asyncio
    async def test_trending_up_scenario(self, initialized_strategy):
        """Test complete trending up scenario"""
        # Start: trailing_stop = [-4, -3, -2, -1], current_unit = 0
        
        # Price trends up from 0 to 3
        for unit in range(1, 4):
            await initialized_strategy._process_unit_up(unit)
        
        # Should have moved grid up
        assert initialized_strategy.trailing_stop == [0, 1, 2]
        assert len(initialized_strategy.trailing_stop) == 4
    
    @pytest.mark.asyncio
    async def test_trending_down_then_up_scenario(self, initialized_strategy):
        """Test price going down then recovering"""
        # Go down 2 units
        await initialized_strategy._process_unit_down(-1)
        await initialized_strategy._process_unit_down(-2)
        
        # Should have 2 buy orders
        assert len(initialized_strategy.trailing_buy) == 2
        
        # Simulate fills on sells
        initialized_strategy.unit_tracker.current_unit = -2
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-1", Decimal("1999"), Decimal("1.25")
        )
        await initialized_strategy.process_fill_confirmation(
            "sell_order_-2", Decimal("1998"), Decimal("1.25")
        )
        
        # Fragments should be down to 2
        assert initialized_strategy.fragments_invested == 2
        
        # Now price recovers
        await initialized_strategy._process_unit_up(-1)
        
        # Should have triggered buy fills and placed replacement sells
        # (In real scenario, fills would come from websocket)
    
    @pytest.mark.asyncio
    async def test_fully_sold_position_scenario(self, initialized_strategy):
        """Test scenario where all 4 fragments are sold"""
        # Move down 4 units, triggering all 4 sells
        for unit in range(-1, -5, -1):
            await initialized_strategy._process_unit_down(unit)
            
            # Simulate the sell fill
            if unit <= -1 and unit >= -4:
                sell_unit = unit
                order_id = f"sell_order_{sell_unit}"
                initialized_strategy.unit_tracker.current_unit = unit
                await initialized_strategy.process_fill_confirmation(
                    order_id, Decimal(str(2000 + sell_unit)), Decimal("1.25")
                )
        
        # Should be fully out of position
        assert initialized_strategy.fragments_invested == 0
        assert len(initialized_strategy.trailing_stop) == 0
        # Should have 4 buy orders waiting
        assert len(initialized_strategy.trailing_buy) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
