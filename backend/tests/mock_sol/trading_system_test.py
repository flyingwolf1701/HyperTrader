#!/usr/bin/env python3
"""
Complete Trading System Test with Mock SOL Data
Integrates mock WebSocket client with your existing HyperTrader system

Run this to test your complete trading strategy with realistic SOL data
"""

import asyncio
import sys
import os
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add backend src to path
backend_dir = Path(__file__).parent.parent / "backend"
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

# Import your trading system
from strategy.position_map import (
    PositionState, 
    PositionConfig,
    calculate_initial_position_map,
    get_active_orders,
    get_window_orders
)
from strategy.unit_tracker import UnitTracker, Phase
from exchange.hyperliquid_sdk import HyperliquidClient, OrderResult


class MockHyperliquidClient:
    """Mock SDK client for testing"""
    
    def __init__(self, use_testnet: bool = True, use_sub_wallet: bool = False):
        self.use_testnet = use_testnet
        self.use_sub_wallet = use_sub_wallet
        self.positions = {}
        self.orders = {}
        self.order_counter = 2000
        
        # Mock SOL data matching your command parameters
        self.sol_price = Decimal("150.00")
        self.sol_position = Decimal("13.333333")  # $2000 / $150
        
        logger.info(f"MockSDK initialized - Testnet: {use_testnet}, SubWallet: {use_sub_wallet}")
    
    def get_user_address(self) -> str:
        wallet_type = "sub" if self.use_sub_wallet else "main"
        return f"0x1234567890abcdef1234567890abcdef1234567{wallet_type}"
    
    def get_current_price(self, symbol: str) -> Decimal:
        if symbol == "SOL":
            return self.sol_price
        return Decimal("100.0")
    
    def get_positions(self) -> dict:
        return {
            "SOL": MockPosition(
                symbol="SOL",
                is_long=True,
                size=self.sol_position,
                entry_price=Decimal("150.00"),
                unrealized_pnl=Decimal("0.0"),
                margin_used=Decimal("100.0")  # $2000 / 20x leverage
            )
        }
    
    def get_position(self, symbol: str):
        positions = self.get_positions()
        return positions.get(symbol)
    
    def place_stop_order(self, symbol: str, is_buy: bool, size: Decimal, 
                        trigger_price: Decimal, reduce_only: bool = True) -> OrderResult:
        """Mock stop order placement"""
        self.order_counter += 1
        order_id = str(self.order_counter)
        
        # Simulate order placement
        action = "BUY" if is_buy else "SELL"
        logger.info(f"📋 Mock STOP ORDER: {action} {size:.6f} {symbol} triggers @ ${trigger_price:.2f}")
        
        return OrderResult(
            success=True,
            order_id=order_id,
            filled_size=Decimal("0"),
            average_price=trigger_price
        )
    
    def place_limit_order(self, symbol: str, is_buy: bool, price: Decimal, 
                         size: Decimal, reduce_only: bool = False, post_only: bool = True) -> OrderResult:
        """Mock limit order placement"""
        self.order_counter += 1
        order_id = str(self.order_counter)
        
        action = "BUY" if is_buy else "SELL"
        logger.info(f"📋 Mock LIMIT ORDER: {action} {size:.6f} {symbol} @ ${price:.2f}")
        
        return OrderResult(
            success=True,
            order_id=order_id,
            filled_size=Decimal("0"),
            average_price=price
        )
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Mock order cancellation"""
        logger.info(f"❌ Mock CANCEL ORDER: {symbol} order {order_id}")
        return True
    
    def open_position(self, symbol: str, usd_amount: Decimal, is_long: bool = True, 
                     leverage: int = None, slippage: float = 0.01) -> OrderResult:
        """Mock position opening"""
        size = usd_amount / self.get_current_price(symbol)
        action = "LONG" if is_long else "SHORT"
        
        logger.info(f"📈 Mock OPEN POSITION: {action} {size:.6f} {symbol} (${usd_amount})")
        
        return OrderResult(
            success=True,
            order_id=str(self.order_counter + 1),
            filled_size=size,
            average_price=self.get_current_price(symbol)
        )


class MockPosition:
    """Mock position object"""
    def __init__(self, symbol: str, is_long: bool, size: Decimal, entry_price: Decimal, 
                 unrealized_pnl: Decimal, margin_used: Decimal):
        self.symbol = symbol
        self.is_long = is_long
        self.size = size
        self.entry_price = entry_price
        self.unrealized_pnl = unrealized_pnl
        self.margin_used = margin_used
    
    @property
    def side(self) -> str:
        return "LONG" if self.is_long else "SHORT"


class TradingSystemTester:
    """Complete trading system test runner"""
    
    def __init__(self):
        self.symbol = "SOL"
        self.wallet_type = "long"
        self.unit_size_usd = Decimal("0.1")
        self.position_size_usd = Decimal("2000")
        self.leverage = 20
        
        # Initialize components
        self.mock_sdk = None
        self.mock_ws = None
        self.position_state = None
        self.position_map = None
        self.unit_tracker = None
        
        # Test tracking
        self.test_events = []
        self.phase_transitions = []
        self.order_executions = []
        
        logger.info(f"TradingSystemTester initialized for {self.symbol}")
    
    async def initialize_system(self):
        """Initialize the complete trading system with mocks"""
        logger.info("🚀 Initializing trading system with mocks...")
        
        # Initialize mock SDK
        self.mock_sdk = MockHyperliquidClient(use_testnet=True, use_sub_wallet=False)
        
        # Get current price and calculate position
        current_price = self.mock_sdk.get_current_price(self.symbol)
        asset_size = self.position_size_usd / current_price
        
        # Initialize position map
        self.position_state, self.position_map = calculate_initial_position_map(
            entry_price=current_price,
            unit_size_usd=self.unit_size_usd,
            asset_size=asset_size,
            position_value_usd=self.position_size_usd,
            unit_range=20
        )
        
        # Initialize unit tracker
        self.unit_tracker = UnitTracker(
            position_state=self.position_state,
            position_map=self.position_map,
            wallet_type=self.wallet_type
        )
        
        # Initialize mock WebSocket
        from mock_websocket_client import MockHyperliquidWebSocketClient
        self.mock_ws = MockHyperliquidWebSocketClient(mock_data_file="sol_mock_data.json")
        
        if await self.mock_ws.connect():
            # Subscribe with callbacks
            await self.mock_ws.subscribe_to_trades(
                symbol=self.symbol,
                unit_size_usd=self.unit_size_usd,
                unit_tracker=self.unit_tracker,
                price_callback=self._handle_price_update,
                fill_callback=self._handle_order_fill
            )
            
            logger.info("✅ Trading system initialized successfully")
            return True
        else:
            logger.error("❌ Failed to initialize mock WebSocket")
            return False
    
    def _handle_price_update(self, price: Decimal):
        """Handle price updates and unit changes"""
        old_unit = self.unit_tracker.current_unit
        old_phase = self.unit_tracker.phase
        
        # Check for unit boundary crossing
        unit_event = self.unit_tracker.calculate_unit_change(price)
        
        if unit_event:
            new_unit = self.unit_tracker.current_unit
            new_phase = self.unit_tracker.phase
            
            logger.warning(f"🎯 UNIT CHANGE: {old_unit} → {new_unit} | {old_phase} → {new_phase}")
            
            # Record phase transition
            if old_phase != new_phase:
                transition = {
                    "timestamp": datetime.now().isoformat(),
                    "old_phase": old_phase.value,
                    "new_phase": new_phase.value,
                    "price": price,
                    "unit": new_unit
                }
                self.phase_transitions.append(transition)
                logger.info(f"📋 PHASE TRANSITION: {old_phase.value} → {new_phase.value}")
            
            # Simulate sliding window management
            asyncio.create_task(self._handle_unit_change(unit_event))
        
        # Record price event
        self.test_events.append({
            "type": "price_update",
            "timestamp": datetime.now().isoformat(),
            "price": str(price),
            "unit": self.unit_tracker.current_unit,
            "phase": self.unit_tracker.phase.value
        })
    
    async def _handle_unit_change(self, unit_event):
        """Handle unit change events"""
        direction = unit_event.direction
        phase = unit_event.phase
        current_unit = self.unit_tracker.current_unit
        
        logger.info(f"🔄 Handling unit change: {direction} in {phase.value} phase")
        
        # Simulate sliding window behavior
        if phase == Phase.ADVANCE and direction == "up":
            await self._slide_window_up_advance(current_unit)
        elif phase == Phase.DECLINE and direction == "down":
            await self._slide_window_down_decline(current_unit)
        
        # Get window state for monitoring
        window_state = self.unit_tracker.get_window_state()
        logger.debug(f"Window state: {window_state}")
    
    async def _slide_window_up_advance(self, current_unit: int):
        """Simulate sliding window up in ADVANCE phase"""
        new_unit = current_unit - 1
        old_unit = current_unit - 5
        
        logger.info(f"📈 ADVANCE slide: Add stop at {new_unit}, cancel at {old_unit}")
        
        # Cancel old order
        if old_unit in self.position_map and self.position_map[old_unit].is_active:
            success = self.mock_sdk.cancel_order(self.symbol, self.position_map[old_unit].order_id)
            if success:
                self.position_map[old_unit].mark_cancelled()
        
        # Place new stop order
        if new_unit in self.position_map:
            trigger_price = self.position_map[new_unit].price
            size = self.position_state.long_fragment_asset
            
            result = self.mock_sdk.place_stop_order(
                symbol=self.symbol,
                is_buy=False,
                size=size,
                trigger_price=trigger_price,
                reduce_only=True
            )
            
            if result.success:
                self.position_map[new_unit].set_active_order(
                    result.order_id, "STOP_SELL", in_window=True
                )
    
    async def _slide_window_down_decline(self, current_unit: int):
        """Simulate sliding window down in DECLINE phase"""
        new_unit = current_unit + 1
        old_unit = current_unit + 5
        
        logger.info(f"📉 DECLINE slide: Add buy at {new_unit}, cancel at {old_unit}")
        
        # Cancel old order
        if old_unit in self.position_map and self.position_map[old_unit].is_active:
            success = self.mock_sdk.cancel_order(self.symbol, self.position_map[old_unit].order_id)
            if success:
                self.position_map[old_unit].mark_cancelled()
        
        # Place new limit buy order
        if new_unit in self.position_map:
            price = self.position_map[new_unit].price
            size = self.position_state.long_fragment_usd / price
            
            result = self.mock_sdk.place_limit_order(
                symbol=self.symbol,
                is_buy=True,
                price=price,
                size=size,
                reduce_only=False,
                post_only=True
            )
            
            if result.success:
                self.position_map[new_unit].set_active_order(
                    result.order_id, "LIMIT_BUY", in_window=True
                )
    
    async def _handle_order_fill(self, order_id: str, is_buy: bool, price: Decimal, 
                                size: Decimal, timestamp: int):
        """Handle order fill notifications"""
        action = "BUY" if is_buy else "SELL"
        logger.warning(f"💰 ORDER FILLED: {action} {size:.6f} {self.symbol} @ ${price:.2f}")
        
        # Find which unit was filled
        filled_unit = None
        for unit, config in self.position_map.items():
            if config.order_id == order_id:
                filled_unit = unit
                config.mark_filled(price, size)
                break
        
        if filled_unit is not None:
            # Handle order replacement logic
            order_type = "sell" if not is_buy else "buy"
            self.unit_tracker.handle_order_execution(filled_unit, order_type)
            
            # Record execution
            execution = {
                "timestamp": datetime.now().isoformat(),
                "order_id": order_id,
                "unit": filled_unit,
                "action": action,
                "size": str(size),
                "price": str(price),
                "phase": self.unit_tracker.phase.value
            }
            self.order_executions.append(execution)
    
    async def run_complete_test(self):
        """Run the complete trading system test"""
        logger.info("🧪 Starting complete trading system test...")
        
        if not await self.initialize_system():
            logger.error("❌ Failed to initialize system")
            return False
        
        # Generate mock data if not exists
        mock_file = Path("sol_mock_data.json")
        if not mock_file.exists():
            logger.info("📝 Generating mock data...")
            from sol_mock_data_generator import SOLMockDataGenerator
            generator = SOLMockDataGenerator()
            messages = generator.generate_complete_cycle()
            generator.save_mock_data(messages)
        
        # Set up test monitoring
        logger.info("🎬 Starting mock data playback...")
        
        # Start listening (this will play through all mock data)
        await self.mock_ws.listen()
        
        # Test complete
        await self.mock_ws.disconnect()
        
        # Generate test report
        self.generate_test_report()
        
        logger.info("✅ Complete trading system test finished!")
        return True
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "=" * 60)
        logger.info("TRADING SYSTEM TEST REPORT")
        logger.info("=" * 60)
        
        # Summary
        logger.info(f"📊 SUMMARY:")
        logger.info(f"  Total price updates: {len(self.test_events)}")
        logger.info(f"  Phase transitions: {len(self.phase_transitions)}")
        logger.info(f"  Order executions: {len(self.order_executions)}")
        
        # Phase transitions
        if self.phase_transitions:
            logger.info(f"\n🔄 PHASE TRANSITIONS:")
            for transition in self.phase_transitions:
                logger.info(f"  {transition['old_phase']} → {transition['new_phase']} @ ${transition['price']} (Unit {transition['unit']})")
        
        # Order executions by phase
        if self.order_executions:
            logger.info(f"\n💰 ORDER EXECUTIONS:")
            for execution in self.order_executions:
                logger.info(f"  {execution['phase']}: {execution['action']} {execution['size']} @ ${execution['price']} (Unit {execution['unit']})")
        
        # Fragment consistency check
        logger.info(f"\n🧮 FRAGMENT CONSISTENCY:")
        logger.info(f"  Expected fragment (SOL): {self.position_state.long_fragment_asset:.6f}")
        logger.info(f"  Expected fragment (USD): ${self.position_state.long_fragment_usd:.2f}")
        
        # Window status
        window_state = self.unit_tracker.get_window_state()
        logger.info(f"\n🎯 FINAL WINDOW STATE:")
        logger.info(f"  Current unit: {window_state['current_unit']}")
        logger.info(f"  Current phase: {window_state['phase']}")
        logger.info(f"  Sell orders: {window_state['sell_orders']}")
        logger.info(f"  Buy orders: {window_state['buy_orders']}")
        logger.info(f"  Peak unit: {window_state['peak_unit']}")
        logger.info(f"  Valley unit: {window_state['valley_unit']}")
        
        # Active orders
        active_orders = get_active_orders(self.position_map)
        window_orders = get_window_orders(self.position_map)
        logger.info(f"\n📋 ORDER STATUS:")
        logger.info(f"  Active orders: {len(active_orders)}")
        logger.info(f"  Window orders: {len(window_orders)}")
        
        logger.info("=" * 60)


async def main():
    """Main test runner"""
    print("🚀 SOL Trading Strategy Complete System Test")
    print("=" * 50)
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", 
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    
    # Run test
    tester = TradingSystemTester()
    success = await tester.run_complete_test()
    
    if success:
        print("\n✅ Test completed successfully!")
        print("📋 Check the test report above for detailed results")
        print("🎯 Focus on verifying:")
        print("  - All phase transitions occurred correctly")
        print("  - Fragment sizes remained consistent")
        print("  - Sliding window behavior worked as expected")
        print("  - Order executions happened at correct units")
    else:
        print("\n❌ Test failed - check logs for details")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
