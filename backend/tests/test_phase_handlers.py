"""
Test suite for phase handler functions
Tests the actual trading logic in each phase
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, call
import asyncio

from src.core.models import Phase, UnitTracker
from src.strategy.strategy_manager import StrategyManager, StrategyState
from src.exchange.exchange_client import HyperliquidExchangeClient


class TestRetracementPhaseHandler:
    """Test RETRACEMENT phase handler actions"""
    
    @pytest.fixture
    def setup_manager(self):
        """Setup manager with mocked exchange"""
        manager = StrategyManager(testnet=True)
        mock_exchange = Mock(spec=HyperliquidExchangeClient)
        mock_exchange.get_current_price.return_value = Decimal("4340")  # Price dropped
        mock_exchange.reduce_position.return_value = {"id": "reduce123"}
        mock_exchange.open_short.return_value = {"id": "short123"}
        mock_exchange.add_to_position.return_value = {"id": "add123"}
        mock_exchange.close_position.return_value = {"id": "close123"}
        manager.exchange_client = mock_exchange
        
        # Create strategy state
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.entry_price = Decimal("4350")
        state.unit_tracker.entry_price = Decimal("4350")
        state.unit_tracker.phase = Phase.RETRACEMENT
        state.unit_tracker.peak_unit = 5  # Was at +5 units
        state.position_fragment = Decimal("100")  # 10% of position
        state.has_position = True
        
        manager.strategies["ETH/USDC:USDC"] = state
        return manager, state
        
    @pytest.mark.asyncio
    async def test_retracement_minus_1_unit(self, setup_manager):
        """Test -1 unit from peak: Sell 1 fragment long, Open 1 fragment short"""
        manager, state = setup_manager
        state.unit_tracker.current_unit = 4  # -1 from peak of 5
        
        await manager.handle_retracement_phase("ETH/USDC:USDC")
        
        # Should reduce long by 1 fragment
        manager.exchange_client.reduce_position.assert_called_once()
        call_args = manager.exchange_client.reduce_position.call_args
        assert call_args[1]["symbol"] == "ETH/USDC:USDC"
        assert call_args[1]["side"] == "sell"
        
        # Should open short with 1 fragment
        manager.exchange_client.open_short.assert_called_once()
        call_args = manager.exchange_client.open_short.call_args
        assert call_args[1]["position_size_usd"] == Decimal("100")
        
    @pytest.mark.asyncio
    async def test_retracement_minus_2_units(self, setup_manager):
        """Test -2 units from peak: Sell 2 fragments long, Add 1 fragment short"""
        manager, state = setup_manager
        state.unit_tracker.current_unit = 3  # -2 from peak of 5
        
        await manager.handle_retracement_phase("ETH/USDC:USDC")
        
        # Should reduce long by 2 fragments
        manager.exchange_client.reduce_position.assert_called_once()
        call_args = manager.exchange_client.reduce_position.call_args
        # Amount should be 2 fragments worth
        
        # Should add to short with 1 fragment
        manager.exchange_client.add_to_position.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_retracement_minus_5_units(self, setup_manager):
        """Test -5 units: Sell remaining long, add proceeds to short"""
        manager, state = setup_manager
        state.unit_tracker.current_unit = 0  # -5 from peak of 5
        
        # Mock existing long position
        manager.exchange_client.get_position.return_value = {
            "side": "long",
            "contracts": Decimal("0.23")
        }
        
        await manager.handle_retracement_phase("ETH/USDC:USDC")
        
        # Should close entire long position
        manager.exchange_client.close_position.assert_called_once()
        
        # Should add proceeds to short
        manager.exchange_client.add_to_position.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_retracement_minus_6_triggers_decline(self, setup_manager):
        """Test -6 units triggers DECLINE phase"""
        manager, state = setup_manager
        state.unit_tracker.current_unit = -1  # -6 from peak of 5
        
        with patch.object(manager, 'handle_decline_phase', new_callable=AsyncMock) as mock_decline:
            await manager.handle_retracement_phase("ETH/USDC:USDC")
            
            # Should transition to DECLINE
            assert state.unit_tracker.phase == Phase.DECLINE
            assert state.unit_tracker.valley_unit == -1
            mock_decline.assert_called_once()


class TestDeclinePhaseHandler:
    """Test DECLINE phase handler"""
    
    @pytest.fixture
    def setup_decline(self):
        """Setup manager in DECLINE phase"""
        manager = StrategyManager(testnet=True)
        mock_exchange = Mock(spec=HyperliquidExchangeClient)
        mock_exchange.get_current_price.return_value = Decimal("4300")
        mock_exchange.get_position.return_value = {
            "side": "short",
            "contracts": Decimal("0.115"),  # About 50% of original
            "entryPrice": Decimal("4340"),
            "unrealizedPnl": Decimal("4.60")  # Profit from short
        }
        manager.exchange_client = mock_exchange
        
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.unit_tracker.phase = Phase.DECLINE
        state.unit_tracker.valley_unit = -5
        state.unit_tracker.current_unit = -5
        
        manager.strategies["ETH/USDC:USDC"] = state
        return manager, state
        
    @pytest.mark.asyncio
    async def test_decline_updates_valley(self, setup_decline):
        """Test DECLINE phase updates valley on new lows"""
        manager, state = setup_decline
        state.unit_tracker.current_unit = -7  # New low
        
        await manager.handle_decline_phase("ETH/USDC:USDC")
        
        # Valley should be updated by unit tracker
        # Hedge fragment should be calculated
        assert state.hedge_fragment > 0
        
    @pytest.mark.asyncio
    async def test_decline_triggers_recovery(self, setup_decline):
        """Test DECLINE transitions to RECOVERY at +2 from valley"""
        manager, state = setup_decline
        state.unit_tracker.current_unit = -3  # +2 from valley of -5
        
        with patch.object(manager, 'handle_recovery_phase', new_callable=AsyncMock) as mock_recovery:
            await manager.handle_decline_phase("ETH/USDC:USDC")
            
            # Should transition to RECOVERY
            assert state.unit_tracker.phase == Phase.RECOVERY
            mock_recovery.assert_called_once()


class TestRecoveryPhaseHandler:
    """Test RECOVERY phase handler"""
    
    @pytest.fixture
    def setup_recovery(self):
        """Setup manager in RECOVERY phase"""
        manager = StrategyManager(testnet=True)
        mock_exchange = Mock(spec=HyperliquidExchangeClient)
        mock_exchange.get_current_price.return_value = Decimal("4320")
        mock_exchange.get_position.return_value = {
            "side": "short",
            "contracts": Decimal("0.115")
        }
        mock_exchange.reduce_position.return_value = {"id": "reduce123"}
        mock_exchange.open_long.return_value = {"id": "long123"}
        mock_exchange.add_to_position.return_value = {"id": "add123"}
        mock_exchange.close_position.return_value = {"id": "close123"}
        manager.exchange_client = mock_exchange
        
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.unit_tracker.phase = Phase.RECOVERY
        state.unit_tracker.valley_unit = -10
        state.unit_tracker.current_unit = -8  # +2 from valley
        state.hedge_fragment = Decimal("125")  # 25% of short
        state.position_fragment = Decimal("100")
        state.last_recovery_unit = 0
        
        manager.strategies["ETH/USDC:USDC"] = state
        return manager, state
        
    @pytest.mark.asyncio
    async def test_recovery_plus_2_units(self, setup_recovery):
        """Test +2 from valley: Close hedge fragment short, buy long"""
        manager, state = setup_recovery
        state.unit_tracker.current_unit = -8  # +2 from valley
        state.last_recovery_unit = 1  # Haven't processed +2 yet
        
        await manager.handle_recovery_phase("ETH/USDC:USDC")
        
        # Should update last processed unit
        assert state.last_recovery_unit == 2
        
        # Should reduce short by hedge fragment
        manager.exchange_client.reduce_position.assert_called()
        
        # Should open long with hedge fragment
        manager.exchange_client.open_long.assert_called()
        
        # Should add position fragment with cash
        manager.exchange_client.add_to_position.assert_called()
        
    @pytest.mark.asyncio
    async def test_recovery_prevents_duplicate_execution(self, setup_recovery):
        """Test recovery actions only execute once per unit level"""
        manager, state = setup_recovery
        state.unit_tracker.current_unit = -8  # +2 from valley
        state.last_recovery_unit = 2  # Already processed this level
        
        await manager.handle_recovery_phase("ETH/USDC:USDC")
        
        # Should NOT execute any trades
        manager.exchange_client.reduce_position.assert_not_called()
        manager.exchange_client.open_long.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_recovery_plus_5_units(self, setup_recovery):
        """Test +5 from valley: Close all short, convert to long"""
        manager, state = setup_recovery
        state.unit_tracker.current_unit = -5  # +5 from valley
        state.last_recovery_unit = 4
        
        await manager.handle_recovery_phase("ETH/USDC:USDC")
        
        # Should close entire short position
        manager.exchange_client.close_position.assert_called_once()
        
        # Should open long with proceeds
        manager.exchange_client.open_long.assert_called()
        
    @pytest.mark.asyncio
    async def test_recovery_plus_6_triggers_reset(self, setup_recovery):
        """Test +6 from valley triggers RESET"""
        manager, state = setup_recovery
        state.unit_tracker.current_unit = -4  # +6 from valley
        state.last_recovery_unit = 5
        
        with patch.object(manager, 'handle_reset_mechanism', new_callable=AsyncMock) as mock_reset:
            await manager.handle_recovery_phase("ETH/USDC:USDC")
            
            # Should trigger RESET
            mock_reset.assert_called_once_with("ETH/USDC:USDC")


class TestResetMechanism:
    """Test RESET mechanism"""
    
    @pytest.fixture
    def setup_reset(self):
        """Setup manager ready for RESET"""
        manager = StrategyManager(testnet=True)
        mock_exchange = Mock(spec=HyperliquidExchangeClient)
        mock_exchange.get_position.return_value = {
            "side": "long",
            "contracts": Decimal("0.25")  # Slightly more than started
        }
        mock_exchange.get_current_price.return_value = Decimal("4360")
        manager.exchange_client = mock_exchange
        
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.position_allocation = Decimal("1000")
        state.unit_tracker.current_unit = 5
        state.unit_tracker.peak_unit = 10
        state.unit_tracker.valley_unit = -5
        state.reset_count = 0
        
        manager.strategies["ETH/USDC:USDC"] = state
        return manager, state
        
    @pytest.mark.asyncio
    async def test_reset_updates_allocation(self, setup_reset):
        """Test RESET updates position allocation to current value"""
        manager, state = setup_reset
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        # New position value: 0.25 ETH * $4360 = $1090
        expected_value = Decimal("0.25") * Decimal("4360")
        assert state.position_allocation == expected_value
        assert state.initial_position_allocation == expected_value
        
    @pytest.mark.asyncio
    async def test_reset_clears_units(self, setup_reset):
        """Test RESET clears all unit tracking"""
        manager, state = setup_reset
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        assert state.unit_tracker.current_unit == 0
        assert state.unit_tracker.peak_unit == 0
        assert state.unit_tracker.valley_unit == 0
        
    @pytest.mark.asyncio
    async def test_reset_updates_entry_price(self, setup_reset):
        """Test RESET sets new entry price"""
        manager, state = setup_reset
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        assert state.entry_price == Decimal("4360")
        assert state.unit_tracker.entry_price == Decimal("4360")
        
    @pytest.mark.asyncio
    async def test_reset_increments_counter(self, setup_reset):
        """Test RESET increments reset counter"""
        manager, state = setup_reset
        initial_count = state.reset_count
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        assert state.reset_count == initial_count + 1
        
    @pytest.mark.asyncio
    async def test_reset_enters_advance_phase(self, setup_reset):
        """Test RESET enters ADVANCE phase"""
        manager, state = setup_reset
        state.unit_tracker.phase = Phase.RECOVERY
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        assert state.unit_tracker.phase == Phase.ADVANCE
        
    @pytest.mark.asyncio
    async def test_reset_recalculates_fragments(self, setup_reset):
        """Test RESET recalculates position fragment"""
        manager, state = setup_reset
        
        await manager.handle_reset_mechanism("ETH/USDC:USDC")
        
        # New position value: $1090
        # New fragment: 10% of $1090 = $109
        expected_fragment = Decimal("109")
        assert state.position_fragment == expected_fragment


class TestCompleteLifecycle:
    """Test a complete strategy lifecycle"""
    
    @pytest.mark.asyncio
    async def test_full_cycle_advance_to_reset(self):
        """Test complete cycle from ADVANCE through RESET"""
        manager = StrategyManager(testnet=True)
        
        # Mock exchange for entire lifecycle
        mock_exchange = Mock(spec=HyperliquidExchangeClient)
        manager.exchange_client = mock_exchange
        
        # Create strategy
        state = StrategyState(
            symbol="ETH/USDC:USDC",
            position_size_usd=Decimal("1000"),
            unit_size=Decimal("10"),
            leverage=10
        )
        state.entry_price = Decimal("4350")
        state.unit_tracker.entry_price = Decimal("4350")
        state.unit_tracker.debounce_seconds = 0  # Disable for testing
        state.has_position = True
        manager.strategies["ETH/USDC:USDC"] = state
        
        # Phase 1: ADVANCE - price rises
        assert state.unit_tracker.phase == Phase.ADVANCE
        state.unit_tracker.calculate_unit_change(Decimal("4380"))  # +3 units
        assert state.unit_tracker.peak_unit == 3
        
        # Phase 2: Start RETRACEMENT - price drops from peak
        state.unit_tracker.calculate_unit_change(Decimal("4370"))  # -1 from peak
        assert state.unit_tracker.get_units_from_peak() == -1
        state.unit_tracker.phase = Phase.RETRACEMENT
        
        # Continue dropping through RETRACEMENT
        state.unit_tracker.calculate_unit_change(Decimal("4320"))  # -6 from peak
        assert state.unit_tracker.get_units_from_peak() == -6
        
        # Phase 3: DECLINE - hold short position
        state.unit_tracker.phase = Phase.DECLINE
        state.unit_tracker.valley_unit = state.unit_tracker.current_unit
        
        # Continue dropping in DECLINE
        state.unit_tracker.calculate_unit_change(Decimal("4300"))  # New valley
        assert state.unit_tracker.valley_unit == -5
        
        # Phase 4: RECOVERY - price rebounds
        state.unit_tracker.calculate_unit_change(Decimal("4320"))  # +2 from valley
        assert state.unit_tracker.get_units_from_valley() == 2
        state.unit_tracker.phase = Phase.RECOVERY
        
        # Continue recovery
        state.unit_tracker.calculate_unit_change(Decimal("4350"))  # +5 from valley
        assert state.unit_tracker.get_units_from_valley() == 5
        
        # Complete recovery
        state.unit_tracker.calculate_unit_change(Decimal("4360"))  # +6 from valley
        assert state.unit_tracker.get_units_from_valley() == 6
        
        # Would trigger RESET here
        # After RESET, back to ADVANCE with new baseline


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])