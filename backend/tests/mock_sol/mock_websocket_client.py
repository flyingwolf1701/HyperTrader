#!/usr/bin/env python3
"""
Mock WebSocket Client for Testing SOL Trading Strategy
Replaces the real WebSocket client with mock data playback

This allows testing the complete trading cycle without connecting to Hyperliquid
"""

import asyncio
import json
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from loguru import logger
from pathlib import Path


class MockHyperliquidWebSocketClient:
    """Mock WebSocket client that plays back recorded data"""
    
    def __init__(self, testnet: bool = True, user_address: Optional[str] = None, mock_data_file: str = "sol_mock_data.json"):
        self.testnet = testnet
        self.user_address = user_address
        self.mock_data_file = mock_data_file
        self.is_connected = False
        
        # Callback storage
        self.price_callbacks = {}  # Dict[symbol, callable]
        self.fill_callbacks = {}   # Dict[symbol, callable]
        self.unit_trackers = {}    # Dict[symbol, UnitTracker]
        
        # Mock data
        self.mock_data = None
        self.mock_messages = []
        self.current_message_index = 0
        
        # Playback control
        self.playback_speed = 1.0  # 1.0 = real time, 2.0 = 2x speed, 0.5 = half speed
        self.auto_play = True      # Whether to auto-advance messages
        self.playback_task = None
        
        logger.info(f"MockWebSocketClient initialized with data file: {mock_data_file}")
    
    async def connect(self) -> bool:
        """Mock connection - loads mock data"""
        try:
            self._load_mock_data()
            self.is_connected = True
            logger.info("✅ Mock WebSocket connected successfully")
            logger.info(f"Loaded {len(self.mock_messages)} mock messages")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect mock WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Mock disconnection"""
        self.is_connected = False
        if self.playback_task and not self.playback_task.done():
            self.playback_task.cancel()
            try:
                await self.playback_task
            except asyncio.CancelledError:
                pass
        logger.info("🔌 Mock WebSocket disconnected")
    
    def _load_mock_data(self):
        """Load mock data from JSON file"""
        mock_file = Path(self.mock_data_file)
        if not mock_file.exists():
            raise FileNotFoundError(f"Mock data file not found: {self.mock_data_file}")
        
        with open(mock_file, 'r') as f:
            self.mock_data = json.load(f)
        
        self.mock_messages = self.mock_data.get("messages", [])
        metadata = self.mock_data.get("metadata", {})
        
        logger.info(f"Mock data metadata:")
        logger.info(f"  Symbol: {metadata.get('symbol')}")
        logger.info(f"  Entry price: ${metadata.get('entry_price')}")
        logger.info(f"  Position size: {metadata.get('position_size_sol')} SOL")
        logger.info(f"  Unit size: ${metadata.get('unit_size_usd')}")
        logger.info(f"  Generated: {metadata.get('generated_at')}")
    
    async def subscribe_to_user_fills(self, user_address: str) -> bool:
        """Mock subscription to user fills"""
        logger.info(f"📋 Mock subscribed to user fills for: {user_address}")
        return True
    
    async def subscribe_to_trades(self, symbol: str, unit_size_usd: Decimal = Decimal("0.1"), 
                                 unit_tracker=None, price_callback: callable = None, 
                                 fill_callback: callable = None) -> bool:
        """Mock subscription to trades"""
        if unit_tracker:
            self.unit_trackers[symbol] = unit_tracker
        
        if price_callback:
            self.price_callbacks[symbol] = price_callback
        
        if fill_callback:
            self.fill_callbacks[symbol] = fill_callback
        
        logger.info(f"📈 Mock subscribed to {symbol} trades")
        logger.info(f"  Unit size: ${unit_size_usd}")
        logger.info(f"  Price callback: {'✅' if price_callback else '❌'}")
        logger.info(f"  Fill callback: {'✅' if fill_callback else '❌'}")
        
        return True
    
    async def listen(self):
        """Mock listen - starts playback of mock messages"""
        if not self.is_connected:
            logger.error("❌ Mock WebSocket not connected")
            return
        
        logger.info("🎬 Starting mock data playback...")
        
        if self.auto_play:
            self.playback_task = asyncio.create_task(self._auto_playback())
            try:
                await self.playback_task
            except asyncio.CancelledError:
                logger.info("⏹️ Mock playback cancelled")
        else:
            logger.info("⏸️ Manual playback mode - use step_forward() to advance")
            
    async def _auto_playback(self):
        """Automatically play back all messages with timing"""
        previous_timestamp = None
        
        for i, message in enumerate(self.mock_messages):
            if not self.is_connected:
                break
                
            # Calculate delay based on timestamps
            current_timestamp = message.get("timestamp")
            if previous_timestamp and current_timestamp:
                try:
                    prev_dt = datetime.fromisoformat(previous_timestamp)
                    curr_dt = datetime.fromisoformat(current_timestamp)
                    delay = (curr_dt - prev_dt).total_seconds()
                    delay = max(0.1, delay / self.playback_speed)  # Min 0.1s delay
                    await asyncio.sleep(delay)
                except:
                    await asyncio.sleep(1.0)  # Default delay
            
            # Process the message
            self.current_message_index = i
            await self._process_mock_message(message)
            previous_timestamp = current_timestamp
            
        logger.info("🎬 Mock data playback complete!")
    
    async def step_forward(self) -> bool:
        """Manually advance to next message (for manual testing)"""
        if self.current_message_index >= len(self.mock_messages):
            logger.info("📄 End of mock data reached")
            return False
        
        message = self.mock_messages[self.current_message_index]
        await self._process_mock_message(message)
        self.current_message_index += 1
        
        logger.info(f"👆 Advanced to message {self.current_message_index}/{len(self.mock_messages)}")
        return True
    
    async def _process_mock_message(self, message: Dict[str, Any]):
        """Process a single mock message"""
        channel = message.get("channel")
        phase = message.get("phase", "UNKNOWN")
        unit = message.get("unit")
        
        if channel == "trades":
            await self._handle_mock_trades(message)
        elif channel == "userFills":
            await self._handle_mock_fills(message)
        else:
            logger.debug(f"Unknown mock message type: {channel}")
    
    async def _handle_mock_trades(self, message: Dict[str, Any]):
        """Handle mock trade data"""
        data = message.get("data", [])
        if not data:
            return
            
        trade = data[0]
        coin = trade.get("coin")
        price_str = trade.get("px")
        phase = message.get("phase", "UNKNOWN")
        unit = message.get("unit")
        
        if coin and price_str:
            price = Decimal(price_str)
            
            logger.info(f"📊 {phase} | Unit {unit} | {coin}: ${price}")
            
            # Call price callback if registered
            if coin in self.price_callbacks and self.price_callbacks[coin]:
                logger.debug(f"🔄 Calling price callback for {coin}")
                self.price_callbacks[coin](price)
    
    async def _handle_mock_fills(self, message: Dict[str, Any]):
        """Handle mock fill data"""
        data = message.get("data", {})
        fills = data.get("fills", [])
        
        if not fills:
            return
            
        fill = fills[0]
        coin = fill.get("coin")
        order_id = fill.get("oid")
        price_str = fill.get("px")
        size_str = fill.get("sz")
        side = fill.get("side")
        order_type = message.get("order_type", "UNKNOWN")
        phase = message.get("phase", "UNKNOWN")
        unit = message.get("unit")
        
        if coin and price_str and size_str:
            price = Decimal(price_str)
            size = abs(Decimal(size_str))
            is_buy = side == "B" or float(size_str) > 0
            
            action = "BUY" if is_buy else "SELL"
            logger.warning(f"💰 {phase} | Unit {unit} | {order_type} FILL: {action} {size:.6f} {coin} @ ${price}")
            
            # Call fill callback if registered
            if coin in self.fill_callbacks and self.fill_callbacks[coin]:
                logger.debug(f"🔄 Calling fill callback for {coin}")
                await self.fill_callbacks[coin](
                    order_id=str(order_id),
                    is_buy=is_buy,
                    price=price,
                    size=size,
                    timestamp=int(time.time() * 1000)
                )
    
    def set_playback_speed(self, speed: float):
        """Set playback speed multiplier"""
        self.playback_speed = max(0.1, speed)
        logger.info(f"⚡ Playback speed set to {self.playback_speed}x")
    
    def get_playback_status(self) -> Dict[str, Any]:
        """Get current playback status"""
        return {
            "connected": self.is_connected,
            "total_messages": len(self.mock_messages),
            "current_index": self.current_message_index,
            "progress_pct": (self.current_message_index / len(self.mock_messages)) * 100 if self.mock_messages else 0,
            "auto_play": self.auto_play,
            "playback_speed": self.playback_speed
        }
    
    def jump_to_phase(self, phase: str) -> bool:
        """Jump to the start of a specific phase"""
        for i, message in enumerate(self.mock_messages):
            if message.get("phase") == phase:
                self.current_message_index = i
                logger.info(f"🦘 Jumped to {phase} phase (message {i})")
                return True
        
        logger.warning(f"Phase '{phase}' not found in mock data")
        return False
    
    def list_phases(self) -> List[str]:
        """List all phases available in mock data"""
        phases = set()
        for message in self.mock_messages:
            phase = message.get("phase")
            if phase:
                phases.add(phase)
        return sorted(list(phases))


class MockTradingTestHarness:
    """Test harness for running mock trading scenarios"""
    
    def __init__(self, mock_data_file: str = "sol_mock_data.json"):
        self.mock_ws = MockHyperliquidWebSocketClient(mock_data_file=mock_data_file)
        self.test_results = []
    
    async def run_phase_test(self, phase: str) -> Dict[str, Any]:
        """Run test for a specific phase"""
        logger.info(f"🧪 Testing {phase} phase...")
        
        # Jump to phase
        if not self.mock_ws.jump_to_phase(phase):
            return {"success": False, "error": f"Phase {phase} not found"}
        
        # Track events during phase
        phase_events = []
        original_index = self.mock_ws.current_message_index
        
        # Step through phase messages
        while self.mock_ws.current_message_index < len(self.mock_ws.mock_messages):
            message = self.mock_ws.mock_messages[self.mock_ws.current_message_index]
            if message.get("phase") != phase:
                break
                
            await self.mock_ws.step_forward()
            phase_events.append(message)
        
        result = {
            "success": True,
            "phase": phase,
            "events_processed": len(phase_events),
            "start_index": original_index,
            "end_index": self.mock_ws.current_message_index
        }
        
        self.test_results.append(result)
        logger.info(f"✅ {phase} phase test complete: {len(phase_events)} events")
        return result
    
    async def run_full_cycle_test(self) -> Dict[str, Any]:
        """Run complete cycle test"""
        logger.info("🔄 Running full cycle test...")
        
        phases = self.mock_ws.list_phases()
        results = {}
        
        for phase in phases:
            results[phase] = await self.run_phase_test(phase)
        
        logger.info(f"🏁 Full cycle test complete: {len(phases)} phases tested")
        return results


# Usage example and test script
async def main():
    """Example usage of mock WebSocket client"""
    print("🧪 SOL Trading Strategy Mock Test")
    print("=" * 40)
    
    # Generate mock data first
    from sol_mock_data_generator import SOLMockDataGenerator
    
    generator = SOLMockDataGenerator()
    messages = generator.generate_complete_cycle()
    filename = generator.save_mock_data(messages)
    
    print(f"\n📁 Mock data generated: {filename}")
    
    # Test mock WebSocket client
    mock_ws = MockHyperliquidWebSocketClient(mock_data_file=filename)
    
    # Define test callbacks
    def price_callback(price: Decimal):
        print(f"💰 Price update: ${price}")
    
    async def fill_callback(order_id: str, is_buy: bool, price: Decimal, size: Decimal, timestamp: int):
        action = "BUY" if is_buy else "SELL"
        print(f"📈 Order filled: {action} {size:.6f} SOL @ ${price} (ID: {order_id})")
    
    # Connect and subscribe
    if await mock_ws.connect():
        await mock_ws.subscribe_to_trades("SOL", Decimal("0.1"), None, price_callback, fill_callback)
        
        # Manual testing example
        print(f"\n🎮 Manual playback test:")
        print(f"Available phases: {mock_ws.list_phases()}")
        
        # Jump to RETRACEMENT phase
        mock_ws.jump_to_phase("RETRACEMENT")
        
        # Step through a few messages
        for i in range(5):
            if await mock_ws.step_forward():
                await asyncio.sleep(0.5)
            else:
                break
        
        print(f"\n📊 Playback status: {mock_ws.get_playback_status()}")
        
        await mock_ws.disconnect()
    
    print("\n✅ Mock test complete!")


if __name__ == "__main__":
    import time
    asyncio.run(main())
