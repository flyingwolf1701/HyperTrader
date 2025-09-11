#!/usr/bin/env python3
"""
SOL Trading Mock Data Generator
Creates realistic WebSocket data for testing all phases of the sliding window strategy

Based on your trade parameters:
- Symbol: SOL
- Position size: $2000
- Leverage: 20x
- Unit size: $0.1
- Wallet: long

This will generate a complete market cycle through all phases:
ADVANCE → RETRACEMENT → DECLINE → RECOVER → RESET
"""

import json
import time
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Any


class SOLMockDataGenerator:
    """Generate realistic SOL trading mock data for all strategy phases"""
    
    def __init__(self):
        # Trade parameters from your command
        self.symbol = "SOL"
        self.position_size_usd = Decimal("2000")
        self.leverage = 20
        self.unit_size_usd = Decimal("0.1")
        
        # Starting conditions
        self.entry_price = Decimal("150.00")  # Realistic SOL price
        self.position_size_sol = self.position_size_usd / self.entry_price  # ~13.33 SOL
        self.long_fragment_sol = self.position_size_sol / Decimal("4")  # ~3.33 SOL per fragment
        self.long_fragment_usd = self.position_size_usd / Decimal("4")  # $500 per fragment
        
        # Mock user address and order IDs
        self.user_address = "0x1234567890abcdef1234567890abcdef12345678"
        self.order_id_counter = 1000
        
        print(f"Mock data for SOL trading:")
        print(f"Entry price: ${self.entry_price}")
        print(f"Position size: {self.position_size_sol:.6f} SOL (${self.position_size_usd})")
        print(f"Fragment size: {self.long_fragment_sol:.6f} SOL (${self.long_fragment_usd})")
        print(f"Unit size: ${self.unit_size_usd}")
        print(f"User address: {self.user_address}")
    
    def get_next_order_id(self) -> int:
        """Get next order ID"""
        self.order_id_counter += 1
        return self.order_id_counter
    
    def create_trade_message(self, price: Decimal, volume: Decimal = Decimal("10.0")) -> Dict[str, Any]:
        """Create a WebSocket trade message"""
        return {
            "channel": "trades",
            "data": [{
                "coin": self.symbol,
                "side": "B",  # Buy
                "px": str(price),
                "sz": str(volume),
                "time": int(time.time() * 1000),
                "tid": int(time.time() * 1000000)
            }]
        }
    
    def create_user_fill_message(self, order_id: int, price: Decimal, size: Decimal, is_buy: bool) -> Dict[str, Any]:
        """Create a WebSocket user fill message"""
        return {
            "channel": "userFills",
            "data": {
                "user": self.user_address,
                "fills": [{
                    "coin": self.symbol,
                    "oid": order_id,
                    "px": str(price),
                    "sz": str(size if is_buy else -size),  # Negative for sell
                    "side": "B" if is_buy else "A",
                    "time": int(time.time() * 1000),
                    "startPosition": str(self.position_size_sol),
                    "dir": "Buy" if is_buy else "Sell",
                    "closedPnl": "0.0",
                    "hash": f"0x{hex(int(time.time() * 1000000))[2:]}",
                    "crossed": False,
                    "fee": str(float(size * price * Decimal("0.0002"))),  # 0.02% fee
                    "feeToken": "USDC",
                    "tid": int(time.time() * 1000000)
                }]
            }
        }
    
    def generate_complete_cycle(self) -> List[Dict[str, Any]]:
        """Generate a complete trading cycle through all phases"""
        messages = []
        current_price = self.entry_price
        current_time = datetime.now()
        
        print(f"\n=== GENERATING COMPLETE SOL TRADING CYCLE ===")
        print(f"Starting at: ${current_price} (Unit 0)")
        
        # PHASE 1: ADVANCE - Price moves up, window slides up
        print(f"\n--- PHASE 1: ADVANCE ---")
        print("Price will advance from $150.00 to $151.50 (+15 units)")
        print("This should trigger sliding window with stop-losses")
        
        # Move price up in steps, generating trades at key unit boundaries
        advance_prices = [
            Decimal("150.05"),  # Small move, no unit change
            Decimal("150.10"),  # Unit 1 - first unit change
            Decimal("150.25"),  # Unit 2-3 range
            Decimal("150.40"),  # Unit 4 range
            Decimal("150.60"),  # Unit 6 range
            Decimal("150.85"),  # Unit 8-9 range
            Decimal("151.10"),  # Unit 11 range
            Decimal("151.35"),  # Unit 13-14 range
            Decimal("151.50"),  # Unit 15 - peak
        ]
        
        for i, price in enumerate(advance_prices):
            current_time += timedelta(seconds=30)
            
            # Add trade message
            trade_msg = self.create_trade_message(price)
            trade_msg["timestamp"] = current_time.isoformat()
            trade_msg["phase"] = "ADVANCE"
            trade_msg["unit"] = int((price - self.entry_price) / self.unit_size_usd)
            messages.append(trade_msg)
            
            # Add some brief intervals
            time.sleep(0.1)
        
        peak_price = advance_prices[-1]
        peak_unit = int((peak_price - self.entry_price) / self.unit_size_usd)
        print(f"Peak reached: ${peak_price} (Unit {peak_unit})")
        
        # PHASE 2: RETRACEMENT - Price drops, stop-losses trigger
        print(f"\n--- PHASE 2: RETRACEMENT ---")
        print("Price will retrace from $151.50 to $150.50 (-10 units)")
        print("Stop-losses will trigger at units 14, 13, 12, 11")
        
        retracement_prices = [
            Decimal("151.40"),  # Unit 14 - first stop-loss trigger
            Decimal("151.30"),  # Unit 13 - second stop-loss trigger  
            Decimal("151.20"),  # Unit 12 - third stop-loss trigger
            Decimal("151.10"),  # Unit 11 - fourth stop-loss trigger
            Decimal("151.00"),  # Unit 10
            Decimal("150.80"),  # Unit 8
            Decimal("150.60"),  # Unit 6
            Decimal("150.50"),  # Unit 5 - transition to DECLINE
        ]
        
        stop_loss_units = [14, 13, 12, 11]  # Units where stop-losses trigger
        stop_loss_index = 0
        
        for i, price in enumerate(retracement_prices):
            current_time += timedelta(seconds=45)
            unit = int((price - self.entry_price) / self.unit_size_usd)
            
            # Add trade message
            trade_msg = self.create_trade_message(price)
            trade_msg["timestamp"] = current_time.isoformat()
            trade_msg["phase"] = "RETRACEMENT"
            trade_msg["unit"] = unit
            messages.append(trade_msg)
            
            # Check if stop-loss should trigger
            if stop_loss_index < len(stop_loss_units) and unit <= stop_loss_units[stop_loss_index]:
                current_time += timedelta(seconds=2)
                
                # Create stop-loss execution
                order_id = self.get_next_order_id()
                fill_msg = self.create_user_fill_message(
                    order_id, price, self.long_fragment_sol, False  # Sell
                )
                fill_msg["timestamp"] = current_time.isoformat()
                fill_msg["phase"] = "RETRACEMENT"
                fill_msg["unit"] = unit
                fill_msg["order_type"] = "STOP_LOSS"
                fill_msg["note"] = f"Stop-loss triggered at unit {unit}"
                messages.append(fill_msg)
                
                print(f"Stop-loss triggered: Unit {unit} @ ${price} - Sold {self.long_fragment_sol:.6f} SOL")
                stop_loss_index += 1
            
            time.sleep(0.1)
        
        # PHASE 3: DECLINE - All stops triggered, now in cash, price continues down
        print(f"\n--- PHASE 3: DECLINE ---")
        print("All stop-losses triggered, position is 100% cash")
        print("Price will decline from $150.50 to $149.00 (-15 units)")
        print("Limit buy orders should be placed ahead of price")
        
        decline_prices = [
            Decimal("150.40"),  # Unit 4
            Decimal("150.20"),  # Unit 2
            Decimal("150.00"),  # Unit 0 (back to entry)
            Decimal("149.80"),  # Unit -2
            Decimal("149.50"),  # Unit -5
            Decimal("149.20"),  # Unit -8
            Decimal("149.00"),  # Unit -10 (valley)
        ]
        
        for i, price in enumerate(decline_prices):
            current_time += timedelta(seconds=60)
            unit = int((price - self.entry_price) / self.unit_size_usd)
            
            # Add trade message
            trade_msg = self.create_trade_message(price)
            trade_msg["timestamp"] = current_time.isoformat()
            trade_msg["phase"] = "DECLINE"
            trade_msg["unit"] = unit
            messages.append(trade_msg)
            
            time.sleep(0.1)
        
        valley_price = decline_prices[-1]
        valley_unit = int((valley_price - self.entry_price) / self.unit_size_usd)
        print(f"Valley reached: ${valley_price} (Unit {valley_unit})")
        
        # PHASE 4: RECOVER - Price recovers, limit buys trigger
        print(f"\n--- PHASE 4: RECOVER ---")
        print("Price will recover from $149.00 to $150.60 (+16 units)")
        print("Limit buy orders will trigger at units -9, -8, -7, -6")
        
        recovery_prices = [
            Decimal("149.10"),  # Unit -9 - first buy trigger
            Decimal("149.20"),  # Unit -8 - second buy trigger
            Decimal("149.30"),  # Unit -7 - third buy trigger
            Decimal("149.40"),  # Unit -6 - fourth buy trigger
            Decimal("149.60"),  # Unit -4
            Decimal("149.80"),  # Unit -2
            Decimal("150.00"),  # Unit 0 (back to entry)
            Decimal("150.20"),  # Unit 2
            Decimal("150.40"),  # Unit 4
            Decimal("150.60"),  # Unit 6 - ready for RESET
        ]
        
        buy_trigger_units = [-9, -8, -7, -6]  # Units where limit buys trigger
        buy_trigger_index = 0
        
        for i, price in enumerate(recovery_prices):
            current_time += timedelta(seconds=45)
            unit = int((price - self.entry_price) / self.unit_size_usd)
            
            # Add trade message
            trade_msg = self.create_trade_message(price)
            trade_msg["timestamp"] = current_time.isoformat()
            trade_msg["phase"] = "RECOVER"
            trade_msg["unit"] = unit
            messages.append(trade_msg)
            
            # Check if limit buy should trigger
            if buy_trigger_index < len(buy_trigger_units) and unit >= buy_trigger_units[buy_trigger_index]:
                current_time += timedelta(seconds=2)
                
                # Create limit buy execution
                order_id = self.get_next_order_id()
                buy_size_sol = self.long_fragment_usd / price  # USD amount / price = SOL amount
                fill_msg = self.create_user_fill_message(
                    order_id, price, buy_size_sol, True  # Buy
                )
                fill_msg["timestamp"] = current_time.isoformat()
                fill_msg["phase"] = "RECOVER"
                fill_msg["unit"] = unit
                fill_msg["order_type"] = "LIMIT_BUY"
                fill_msg["note"] = f"Limit buy triggered at unit {unit}"
                messages.append(fill_msg)
                
                print(f"Limit buy triggered: Unit {unit} @ ${price} - Bought {buy_size_sol:.6f} SOL")
                buy_trigger_index += 1
            
            time.sleep(0.1)
        
        # PHASE 5: RESET - Return to 100% long, reset for new cycle
        print(f"\n--- PHASE 5: RESET TRIGGER ---")
        print("All limit buys executed, back to 100% long position")
        print("System should trigger RESET and start new cycle")
        
        current_time += timedelta(seconds=30)
        reset_price = Decimal("150.60")
        reset_unit = int((reset_price - self.entry_price) / self.unit_size_usd)
        
        # Add final trade message to trigger reset
        reset_msg = self.create_trade_message(reset_price)
        reset_msg["timestamp"] = current_time.isoformat()
        reset_msg["phase"] = "RESET"
        reset_msg["unit"] = reset_unit
        reset_msg["note"] = "Position back to 100% long - RESET should trigger"
        messages.append(reset_msg)
        
        print(f"\n=== CYCLE COMPLETE ===")
        print(f"Final price: ${reset_price} (Unit {reset_unit})")
        print(f"Total messages generated: {len(messages)}")
        print(f"Time span: {current_time - datetime.now() + timedelta(minutes=20)}")
        
        return messages
    
    def save_mock_data(self, messages: List[Dict[str, Any]], filename: str = "sol_mock_data.json"):
        """Save mock data to JSON file"""
        data = {
            "metadata": {
                "symbol": self.symbol,
                "entry_price": str(self.entry_price),
                "position_size_usd": str(self.position_size_usd),
                "position_size_sol": str(self.position_size_sol),
                "leverage": self.leverage,
                "unit_size_usd": str(self.unit_size_usd),
                "long_fragment_sol": str(self.long_fragment_sol),
                "long_fragment_usd": str(self.long_fragment_usd),
                "user_address": self.user_address,
                "generated_at": datetime.now().isoformat()
            },
            "messages": messages
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nMock data saved to: {filename}")
        return filename
    
    def generate_phase_summary(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of phases for testing"""
        summary = {
            "ADVANCE": [],
            "RETRACEMENT": [],
            "DECLINE": [],
            "RECOVER": [],
            "RESET": []
        }
        
        for msg in messages:
            phase = msg.get("phase", "UNKNOWN")
            if phase in summary:
                summary[phase].append({
                    "timestamp": msg.get("timestamp"),
                    "unit": msg.get("unit"),
                    "price": msg.get("data", [{}])[0].get("px") if "data" in msg else None,
                    "type": "trade" if msg.get("channel") == "trades" else "fill",
                    "order_type": msg.get("order_type"),
                    "note": msg.get("note")
                })
        
        return summary


def main():
    """Generate and save complete SOL mock data"""
    print("SOL Trading Strategy Mock Data Generator")
    print("=" * 50)
    
    generator = SOLMockDataGenerator()
    
    # Generate complete cycle
    messages = generator.generate_complete_cycle()
    
    # Save to file
    filename = generator.save_mock_data(messages)
    
    # Generate phase summary
    summary = generator.generate_phase_summary(messages)
    
    print(f"\n=== PHASE SUMMARY ===")
    for phase, events in summary.items():
        print(f"\n{phase}: {len(events)} events")
        for event in events[:3]:  # Show first 3 events
            price = event.get("price", "N/A")
            unit = event.get("unit", "N/A")
            note = event.get("note", "")
            print(f"  Unit {unit} @ ${price} - {note}")
        if len(events) > 3:
            print(f"  ... and {len(events) - 3} more events")
    
    print(f"\n=== TESTING INSTRUCTIONS ===")
    print(f"1. Use this mock data with your trading bot")
    print(f"2. Feed WebSocket messages in sequence with delays")
    print(f"3. Verify each phase transition occurs correctly")
    print(f"4. Check that fragments remain consistent (3.33 SOL, $500)")
    print(f"5. Confirm RESET triggers with compound growth")
    print(f"\nMock data file: {filename}")


if __name__ == "__main__":
    main()
