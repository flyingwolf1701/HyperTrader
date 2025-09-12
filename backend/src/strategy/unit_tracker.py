"""
UnitTracker Implementation - Legacy compatibility layer
Most functionality has been moved to strategy_engine.py and position_tracker.py
This file is maintained for backward compatibility
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Set
from loguru import logger
from dataclasses import dataclass, field

# Import from centralized data models
from .data_models import Phase, UnitChangeEvent
    
# SlidingWindow class removed - now using trailing_stop and trailing_buy lists directly


class UnitTracker:
    """
    Tracks unit changes and manages sliding window order system.
    Implements v9.2.6 sliding window strategy.
    """
    
    def __init__(self, 
                 position_state,
                 position_map: Dict[int, any],
                 wallet_type: str = "long"):
        """
        Initialize unit tracker with sliding window management.
        
        Args:
            position_state: Static position configuration
            position_map: Dynamic unit-based order tracking
            wallet_type: 'long' or 'hedge' wallet
        """
        # Validate wallet_type
        if wallet_type not in ["long", "hedge"]:
            raise ValueError(f"wallet_type must be 'long' or 'hedge', got '{wallet_type}'")
        
        self.position_state = position_state
        self.position_map = position_map
        self.wallet_type = wallet_type
        self.current_unit = 0
        self.previous_phase = Phase.ADVANCE  # Track last phase for transitions
        
        # Sliding window management - LIST-BASED TRACKING
        self.trailing_stop: List[int] = []  # Units with active stop-loss orders
        self.trailing_buy: List[int] = []   # Units with active limit buy orders
        self.executed_orders: Set[int] = set()  # Track which units have executed
        
        # Initialize with 4 sell orders for long wallet
        if wallet_type == "long":
            self._initialize_long_window()
        else:
            self._initialize_hedge_window()
        
        if 0 not in self.position_map:
            raise ValueError("Unit 0 missing from position map")
    
    def _initialize_long_window(self):
        """Initialize long wallet with 4 stop-loss orders"""
        self.trailing_stop = [-4, -3, -2, -1]
        self.trailing_buy = []
        self.phase = Phase.ADVANCE
        logger.info(f"Long wallet initialized with stop-losses at {self.trailing_stop}")
    
    def _initialize_hedge_window(self):
        """Initialize hedge wallet for short strategy"""
        # Hedge starts with 1 sell to exit long, then shorts
        self.trailing_stop = [-1]  # To exit long position
        self.trailing_buy = []
        self.phase = Phase.ADVANCE
        logger.info(f"Hedge wallet initialized with stop at {self.trailing_stop}")
    
    def calculate_unit_change(self, current_price: Decimal) -> Optional[UnitChangeEvent]:
        """
        Check if price has crossed a unit boundary and manage sliding window.
        """
        self._ensure_sufficient_units()
        
        previous_unit = self.current_unit
        direction = None
        
        # Check UP boundary
        next_unit_up = self.current_unit + 1
        if next_unit_up in self.position_map:
            price_threshold_up = self.position_map[next_unit_up].price
            if current_price >= price_threshold_up:
                self.current_unit = next_unit_up
                direction = 'up'
        
        # Check DOWN boundary
        next_unit_down = self.current_unit - 1
        if next_unit_down in self.position_map:
            price_threshold_down = self.position_map[next_unit_down].price
            if current_price <= price_threshold_down:
                self.current_unit = next_unit_down
                direction = 'down'
        
        # If unit changed, manage sliding window
        if self.current_unit != previous_unit:
            self._slide_window(direction)
            self._detect_phase_transition()
            
            # Create window composition string
            window_comp = f"{len(self.trailing_stop)}S/{len(self.trailing_buy)}B"
            
            return UnitChangeEvent(
                price=current_price,
                phase=self.phase,
                current_unit=self.current_unit,
                timestamp=datetime.now(),
                direction=direction,
                window_composition=window_comp
            )
        
        return None
    
    def _slide_window(self, direction: str):
        """
        DEPRECATED - Window sliding is now handled in main.py
        This method is kept for backward compatibility only.
        """
        logger.debug(f"_slide_window called with direction={direction} - deprecated, sliding handled in main.py")
        
    
    def handle_order_execution(self, executed_unit: int, order_type: str):
        """
        Handle order execution and replace with opposite type.
        Implements the order replacement logic from v9.2.6.
        
        Args:
            executed_unit: The unit level where order executed
            order_type: 'sell' or 'buy'
        """
        self.executed_orders.add(executed_unit)
        
        if order_type == 'sell':
            # Remove from sell window
            if executed_unit in self.window.sell_orders:
                self.window.sell_orders.remove(executed_unit)
            
            # Add buy order at current+1 (one unit ahead)
            replacement_unit = self.current_unit + 1
            if replacement_unit not in self.window.buy_orders:
                self.window.buy_orders.append(replacement_unit)
                self.window.buy_orders.sort()
            
            logger.info(f"Sell executed at {executed_unit}, placed buy at {replacement_unit}")
        
        elif order_type == 'buy':
            # Remove from buy window
            if executed_unit in self.window.buy_orders:
                self.window.buy_orders.remove(executed_unit)
            
            # Add sell order at current-1 (one unit behind)
            replacement_unit = self.current_unit - 1
            if replacement_unit not in self.window.sell_orders:
                self.window.sell_orders.append(replacement_unit)
                self.window.sell_orders.sort()
            
            logger.info(f"Buy executed at {executed_unit}, placed sell at {replacement_unit}")
        
        # Detect phase transition after execution
        self._detect_phase_transition()
    
    def _detect_phase_transition(self):
        """
        Detect phase based on order composition.
        Uses previous phase to determine correct mixed state.
        """
        new_phase = self.phase
        
        # Determine phase based on window composition
        has_all_stops = len(self.trailing_stop) == 4 and len(self.trailing_buy) == 0
        has_all_buys = len(self.trailing_buy) == 4 and len(self.trailing_stop) == 0
        has_mixed = len(self.trailing_stop) > 0 and len(self.trailing_buy) > 0
        
        if has_all_stops:
            # 4 stop-loss orders = ADVANCE
            new_phase = Phase.ADVANCE
        elif has_all_buys:
            # 4 limit buy orders = DECLINE
            new_phase = Phase.DECLINE
        elif has_mixed:
            # Mixed orders: use previous phase to determine which transition
            if self.previous_phase == Phase.ADVANCE:
                # Coming from ADVANCE → RETRACEMENT
                new_phase = Phase.RETRACEMENT
            elif self.previous_phase == Phase.DECLINE:
                # Coming from DECLINE → RECOVER
                new_phase = Phase.RECOVER
            # If already in mixed phase, stay there
            elif self.phase in [Phase.RETRACEMENT, Phase.RECOVER]:
                new_phase = self.phase
        
        # Check for RESET trigger
        if self._should_reset():
            new_phase = Phase.RESET
        
        # Update phases
        if new_phase != self.phase:
            logger.info(f"Phase transition: {self.phase} → {new_phase}")
            self.previous_phase = self.phase  # Store the old phase
            self.phase = new_phase
    
    def _should_reset(self) -> bool:
        """
        Check if RESET conditions are met.
        RESET when returning to 100% long from mixed phases.
        """
        # For long wallet: All buys executed in RECOVER phase
        if self.wallet_type == "long":
            has_all_stops = len(self.trailing_stop) == 4 and len(self.trailing_buy) == 0
            if self.phase == Phase.RECOVER and has_all_stops:
                return True
            if self.phase == Phase.RETRACEMENT and has_all_stops:
                return True
        
        # For hedge wallet: All covers executed, ready for long entry
        elif self.wallet_type == "hedge":
            # This would be detected by position state, not just orders
            pass
        
        return False
    
    
    def _ensure_sufficient_units(self):
        """
        Ensure we have units for the sliding window (4 ahead and 4 behind).
        """
        from .position_map import add_unit_level
        
        # Ensure we have 5 units ahead and behind for window management
        for offset in range(-5, 6):
            target_unit = self.current_unit + offset
            if target_unit not in self.position_map:
                add_unit_level(self.position_state, self.position_map, target_unit)
    
    
    def get_window_state(self) -> Dict:
        """
        Get current sliding window state for monitoring.
        """
        return {
            'current_unit': self.current_unit,
            'phase': self.phase.value,
            'trailing_stop': self.trailing_stop.copy(),  
            'trailing_buy': self.trailing_buy.copy(),
            'total_orders': len(self.trailing_stop) + len(self.trailing_buy),
            'executed_orders': list(self.executed_orders),
            # Keep old names for backward compatibility
            'sell_orders': self.trailing_stop.copy(),
            'buy_orders': self.trailing_buy.copy()
        }
    
    def reset_for_new_cycle(self, new_entry_price: Optional[Decimal] = None):
        """
        Reset unit tracking and sliding window for a new strategy cycle.
        Implements RESET mechanism from v9.2.6.
        
        Args:
            new_entry_price: Optional new entry price for the cycle
        """
        logger.info("Executing RESET mechanism for new cycle")
        
        # Reset unit counters
        self.current_unit = 0
        
        # Clear execution history
        self.executed_orders.clear()
        
        # Reinitialize sliding window with new lists
        if self.wallet_type == "long":
            self.trailing_stop = [-4, -3, -2, -1]
            self.trailing_buy = []
            
            # Keep old window updated for compatibility
            self.window.sell_orders = self.trailing_stop.copy()
            self.window.buy_orders = []
            
            self.phase = Phase.ADVANCE
            logger.info(f"Reset long wallet with stop-losses at {self.trailing_stop}")
        else:
            # Hedge wallet reset logic
            self.window.sell_orders = [-1]
            self.window.buy_orders = []
            self.phase = Phase.ADVANCE
            logger.info(f"Reset hedge wallet with sell at {self.window.sell_orders}")
    
    # NEW LIST-BASED TRACKING METHODS
    def add_trailing_stop(self, unit: int) -> bool:
        """Add a unit to trailing stop list if not already present"""
        if unit not in self.trailing_stop:
            self.trailing_stop.append(unit)
            self.trailing_stop.sort()  # Keep sorted for readability
            # Update old window for compatibility
            self.window.sell_orders = self.trailing_stop.copy()
            logger.debug(f"Added stop at unit {unit}, trailing_stop: {self.trailing_stop}")
            return True
        return False
    
    def remove_trailing_stop(self, unit: int) -> bool:
        """Remove a unit from trailing stop list"""
        if unit in self.trailing_stop:
            self.trailing_stop.remove(unit)
            # Update old window for compatibility
            self.window.sell_orders = self.trailing_stop.copy()
            logger.debug(f"Removed stop at unit {unit}, trailing_stop: {self.trailing_stop}")
            return True
        return False
    
    def add_trailing_buy(self, unit: int) -> bool:
        """Add a unit to trailing buy list if not already present"""
        if unit not in self.trailing_buy:
            self.trailing_buy.append(unit)
            self.trailing_buy.sort()  # Keep sorted for readability
            # Update old window for compatibility
            self.window.buy_orders = self.trailing_buy.copy()
            logger.debug(f"Added buy at unit {unit}, trailing_buy: {self.trailing_buy}")
            return True
        return False
    
    def remove_trailing_buy(self, unit: int) -> bool:
        """Remove a unit from trailing buy list"""
        if unit in self.trailing_buy:
            self.trailing_buy.remove(unit)
            # Update old window for compatibility
            self.window.buy_orders = self.trailing_buy.copy()
            logger.debug(f"Removed buy at unit {unit}, trailing_buy: {self.trailing_buy}")
            return True
        return False
        
        if new_entry_price:
            self.position_state.entry_price = new_entry_price
            logger.info(f"Updated entry price: ${new_entry_price:.2f}")
        
        logger.info(f"RESET complete - captured compound growth into new cycle")