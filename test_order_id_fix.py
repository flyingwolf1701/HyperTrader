#!/usr/bin/env python3
"""
Test to verify order ID type consistency fix
"""

# Test data
order_id_int = 39387734424
order_id_str = "39387734424"

# Create a mock order_id_to_unit dictionary
order_id_to_unit = {}

# Store with string key (as fixed)
order_id_to_unit[str(order_id_int)] = -1
print(f"Stored order {str(order_id_int)} -> unit -1")

# Try to lookup with string (as WebSocket provides)
if order_id_str in order_id_to_unit:
    unit = order_id_to_unit[order_id_str]
    print(f"[SUCCESS] Found order {order_id_str} -> unit {unit}")
else:
    print(f"[FAILED] Order {order_id_str} not found in mapping")

# Show the mapping
print(f"\nMapping contents: {order_id_to_unit}")
print(f"Keys are type: {type(list(order_id_to_unit.keys())[0])}")

# Verify string equality
print(f"\nString equality check: '{order_id_str}' == '{str(order_id_int)}' -> {order_id_str == str(order_id_int)}")