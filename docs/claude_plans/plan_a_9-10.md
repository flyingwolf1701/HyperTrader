Comprehensive Fix Plan for Trading Strategy                                                                                                                  │ │
│ │                                                                                                                                                              │ │
│ │ Based on your trading session analysis and test failures, here are the critical fixes needed:                                                                │ │
│ │                                                                                                                                                              │ │
│ │ 1. Fix Stop Order Placement (CRITICAL - All orders executed immediately)                                                                                     │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: Stops are triggering immediately because they're placed at wrong prices                                                                           │ │
│ │ - Fix: Ensure stop losses are ONLY placed at units BELOW current price                                                                                       │ │
│ │ - Implementation: In _place_window_orders(), verify each stop unit price < current_price                                                                     │ │
│ │                                                                                                                                                              │ │
│ │ 2. Fix Unit Jump Calculation (Causes sliding window failures)                                                                                                │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: calculate_unit_change() only moves ±1 unit at a time                                                                                              │ │
│ │ - Fix: Calculate actual target unit: target_unit = int((price - entry_price) / unit_size)                                                                    │ │
│ │ - Handle: Multi-unit jumps by sliding window multiple times if needed                                                                                        │ │
│ │                                                                                                                                                              │ │
│ │ 3. Implement Buy Order Creation After Sells                                                                                                                  │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: After stops execute, no buy orders are created                                                                                                    │ │
│ │ - Fix: Debug _place_limit_order() for buy orders                                                                                                             │ │
│ │ - Verify: Order placement response and error handling                                                                                                        │ │
│ │ - Add: Explicit logging for buy order attempts                                                                                                               │ │
│ │                                                                                                                                                              │ │
│ │ 4. Fix Fragment Size Usage                                                                                                                                   │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: Orders using random sizes instead of calculated 2.25 SOL                                                                                          │ │
│ │ - Fix: Ensure long_fragment_asset is consistently used for all orders                                                                                        │ │
│ │ - Debug: Why different sizes are being sent to exchange                                                                                                      │ │
│ │                                                                                                                                                              │ │
│ │ 5. Implement Rolling Stop Loss                                                                                                                               │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: After sells, stops don't move up to protect profits                                                                                               │ │
│ │ - Fix: After order fills, slide window forward and place new stops                                                                                           │ │
│ │ - Trigger: _slide_window() after each sell execution                                                                                                         │ │
│ │                                                                                                                                                              │ │
│ │ 6. Add State Transition Tracking to Events                                                                                                                   │ │
│ │                                                                                                                                                              │ │
│ │ - Problem: Can't debug what transitions occurred                                                                                                             │ │
│ │ - Fix: Add old_unit and new_unit to UnitChangeEvent                                                                                                          │ │
│ │                                                                                                                                                              │ │
│ │ 7. Fix Test Infrastructure                                                                                                                                   │ │
│ │                                                                                                                                                              │ │
│ │ - Update: Test fixtures to use correct PositionState parameters                                                                                              │ │
│ │ - Add: Network failure handling in order placement                                                                                                           │ │
│ │                                                                                                                                                              │ │
│ │ These fixes address both the immediate trading issues (orders executing incorrectly) and the underlying architectural problems (unit tracking, sliding       │ │
│ │ window).          