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
    
@dataclass
class SlidingWindow:
    """Manages the 4-order sliding window"""
    sell_orders: List[int] = field(default_factory=list)  # Unit levels with sell orders
    buy_orders: List[int] = field(default_factory=list)   # Unit levels with buy orders
    
    def total_orders(self) -> int:
        return len(self.sell_orders) + len(self.buy_orders)
    
    def is_all_sells(self) -> bool:
        return len(self.sell_orders) == 4 and len(self.buy_orders) == 0
    
    def is_all_buys(self) -> bool:
        return len(self.buy_orders) == 4 and len(self.sell_orders) == 0
    
    def is_mixed(self) -> bool:
        return len(self.sell_orders) > 0 and len(self.buy_orders) > 0


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
        
        # Sliding window management
        self.window = SlidingWindow()
        self.executed_orders: Set[int] = set()  # Track which units have executed
        
        # Initialize with 4 sell orders for long wallet
        if wallet_type == "long":
            self._initialize_long_window()
        else:
            self._initialize_hedge_window()
        
        if 0 not in self.position_map:
            raise ValueError("Unit 0 missing from position map")
    
    def _initialize_long_window(self):
        """Initialize long wallet with 4 sell orders"""
        self.window.sell_orders = [-4, -3, -2, -1]
        self.phase = Phase.ADVANCE
        logger.info(f"Long wallet initialized with sells at {self.window.sell_orders}")
    
    def _initialize_hedge_window(self):
        """Initialize hedge wallet for short strategy"""
        # Hedge starts with 1 sell to exit long, then shorts
        self.window.sell_orders = [-1]  # To exit long position
        self.phase = Phase.ADVANCE
        logger.info(f"Hedge wallet initialized with sell at {self.window.sell_orders}")
    
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
            window_comp = f"{len(self.window.sell_orders)}S/{len(self.window.buy_orders)}B"
            
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
        Slide the 4-order window based on price movement.
        Implements the sliding window logic from v9.2.6.
        """
        if direction == 'up':
            # In trending up phases (ADVANCE), slide sell window up
            if self.phase == Phase.ADVANCE and self.window.is_all_sells():
                # Add new sell at current-1, remove sell at current-5
                new_sell = self.current_unit - 1
                old_sell = self.current_unit - 5
                
                if new_sell not in self.window.sell_orders:
                    self.window.sell_orders.append(new_sell)
                    self.window.sell_orders.sort()
                
                if old_sell in self.window.sell_orders:
                    self.window.sell_orders.remove(old_sell)
                
                logger.debug(f"Slid sell window up: {self.window.sell_orders}")
        
        elif direction == 'down':
            # In trending down phases (DECLINE), slide buy window down
            if self.phase == Phase.DECLINE and self.window.is_all_buys():
                # Add new buy at current+1, remove buy at current+5
                new_buy = self.current_unit + 1
                old_buy = self.current_unit + 5
                
                if new_buy not in self.window.buy_orders:
                    self.window.buy_orders.append(new_buy)
                    self.window.buy_orders.sort()
                
                if old_buy in self.window.buy_orders:
                    self.window.buy_orders.remove(old_buy)
                
                logger.debug(f"Slid buy window down: {self.window.buy_orders}")
    
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
        if self.window.is_all_sells():
            # 4 stop-loss orders = ADVANCE
            new_phase = Phase.ADVANCE
        elif self.window.is_all_buys():
            # 4 limit buy orders = DECLINE
            new_phase = Phase.DECLINE
        elif self.window.is_mixed():
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
            if self.phase == Phase.RECOVER and self.window.is_all_sells():
                return True
            if self.phase == Phase.RETRACEMENT and self.window.is_all_sells():
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
            'sell_orders': self.window.sell_orders,
            'buy_orders': self.window.buy_orders,
            'total_orders': self.window.total_orders(),
            'executed_orders': list(self.executed_orders)
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
        
        # Reinitialize sliding window
        if self.wallet_type == "long":
            self.window.sell_orders = [-4, -3, -2, -1]
            self.window.buy_orders = []
            self.phase = Phase.ADVANCE
            logger.info(f"Reset long wallet with sells at {self.window.sell_orders}")
        else:
            # Hedge wallet reset logic
            self.window.sell_orders = [-1]
            self.window.buy_orders = []
            self.phase = Phase.ADVANCE
            logger.info(f"Reset hedge wallet with sell at {self.window.sell_orders}")
        
        if new_entry_price:
            self.position_state.entry_price = new_entry_price
            logger.info(f"Updated entry price: ${new_entry_price:.2f}")
        
        logger.info(f"RESET complete - captured compound growth into new cycle")