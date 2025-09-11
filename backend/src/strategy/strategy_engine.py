"""
Strategy Engine for HyperTrader Long Wallet
Encapsulates all trading strategy logic and decision making
"""

from decimal import Decimal
from typing import Optional, Tuple, List, Dict
from loguru import logger
from .data_models import (
    Phase, OrderType, WindowState, PositionState, 
    UnitChangeEvent, OrderFillEvent
)
from .config import LongWalletConfig


class LongWalletStrategy:
    """
    Encapsulates all long wallet strategy logic.
    Makes decisions about order placement, window sliding, and phase transitions.
    """
    
    def __init__(self, position_state: PositionState):
        """
        Initialize the strategy engine.
        
        Args:
            position_state: Static position configuration
        """
        self.position_state = position_state
        self.current_phase = Phase.ADVANCE
        self.windows = WindowState()
        
        # Initialize with 4 stop-loss orders
        self._initialize_windows()
    
    def _initialize_windows(self):
        """Initialize windows with stop-loss orders per configuration"""
        self.windows.stop_loss_orders = list(LongWalletConfig.INITIAL_WINDOW_UNITS)
        self.windows.limit_buy_orders = []
        self.current_phase = Phase.ADVANCE
        logger.info(f"Initialized windows with stop-losses at {self.windows.stop_loss_orders}")
    
    def detect_phase(self, windows: Optional[WindowState] = None) -> Phase:
        """
        Determine current phase based on window composition.
        
        Args:
            windows: Optional window state to check (uses self.windows if not provided)
            
        Returns:
            Current phase based on order composition
        """
        if windows is None:
            windows = self.windows
        
        previous_phase = self.current_phase
        
        # Determine phase based on window composition
        if windows.is_all_stop_losses():
            self.current_phase = Phase.ADVANCE
        elif windows.is_all_limit_buys():
            self.current_phase = Phase.DECLINE
        elif windows.is_mixed():
            # Mixed state - determine if RETRACEMENT or RECOVER
            if previous_phase in [Phase.ADVANCE, Phase.RETRACEMENT]:
                self.current_phase = Phase.RETRACEMENT
            elif previous_phase in [Phase.DECLINE, Phase.RECOVER]:
                self.current_phase = Phase.RECOVER
        
        # Log phase transitions
        if self.current_phase != previous_phase:
            logger.info(f"Phase transition: {previous_phase.value} → {self.current_phase.value}")
        
        return self.current_phase
    
    def get_replacement_order(self, 
                            executed_unit: int, 
                            current_unit: int, 
                            executed_type: OrderType) -> Tuple[int, OrderType]:
        """
        Determine replacement order when one executes.
        Implements the core order replacement logic from v9.4.12.
        
        Args:
            executed_unit: Unit where order executed
            current_unit: Current price unit
            executed_type: Type of order that executed
            
        Returns:
            Tuple of (replacement_unit, replacement_order_type)
        """
        if executed_type == OrderType.STOP_LOSS_SELL:
            # Stop-loss triggered → Place limit buy at current+1
            replacement_unit = current_unit + 1
            replacement_type = OrderType.LIMIT_BUY
            
            # Update windows
            self.windows.remove_stop_loss(executed_unit)
            self.windows.add_limit_buy(replacement_unit)
            
            logger.info(f"Stop-loss at unit {executed_unit} → Limit buy at unit {replacement_unit}")
            
        elif executed_type == OrderType.LIMIT_BUY:
            # Limit buy filled → Place stop-loss at current-1
            replacement_unit = current_unit - 1
            replacement_type = OrderType.STOP_LOSS_SELL
            
            # Update windows
            self.windows.remove_limit_buy(executed_unit)
            self.windows.add_stop_loss(replacement_unit)
            
            logger.info(f"Limit buy at unit {executed_unit} → Stop-loss at unit {replacement_unit}")
            
        else:
            logger.warning(f"Unexpected order type for replacement: {executed_type}")
            return (current_unit, OrderType.STOP_LOSS_SELL)
        
        # Detect phase after order replacement
        self.detect_phase()
        
        return (replacement_unit, replacement_type)
    
    def calculate_window_slide(self, 
                              current_unit: int, 
                              direction: str, 
                              phase: Optional[Phase] = None) -> Tuple[Optional[int], Optional[int], Optional[OrderType]]:
        """
        Calculate which orders to add/remove when sliding window.
        
        Args:
            current_unit: Current price unit
            direction: 'up' or 'down' movement
            phase: Current phase (uses self.current_phase if not provided)
            
        Returns:
            Tuple of (new_order_unit, old_order_unit, order_type)
        """
        if phase is None:
            phase = self.current_phase
        
        if direction == 'up' and phase == Phase.ADVANCE:
            # Sliding up in ADVANCE: Add stop-loss at current-1, remove at current-5
            new_order = current_unit - 1
            old_order = current_unit - 5
            order_type = OrderType.STOP_LOSS_SELL
            
            # Update windows
            if old_order in self.windows.stop_loss_orders:
                self.windows.remove_stop_loss(old_order)
            self.windows.add_stop_loss(new_order)
            
            logger.debug(f"Slide up: Add stop-loss at {new_order}, remove at {old_order}")
            return (new_order, old_order, order_type)
            
        elif direction == 'down' and phase == Phase.DECLINE:
            # Sliding down in DECLINE: Add limit buy at current+1, remove at current+5
            new_order = current_unit + 1
            old_order = current_unit + 5
            order_type = OrderType.LIMIT_BUY
            
            # Update windows
            if old_order in self.windows.limit_buy_orders:
                self.windows.remove_limit_buy(old_order)
            self.windows.add_limit_buy(new_order)
            
            logger.debug(f"Slide down: Add limit buy at {new_order}, remove at {old_order}")
            return (new_order, old_order, order_type)
        
        # No sliding needed in mixed phases
        return (None, None, None)
    
    def should_reset(self, 
                    windows: Optional[WindowState] = None, 
                    phase: Optional[Phase] = None) -> bool:
        """
        Check if RESET conditions are met.
        RESET occurs when returning to 100% long from mixed phases.
        
        Args:
            windows: Window state to check (uses self.windows if not provided)
            phase: Current phase (uses self.current_phase if not provided)
            
        Returns:
            True if RESET should be triggered
        """
        if windows is None:
            windows = self.windows
        if phase is None:
            phase = self.current_phase
        
        # Reset when returning to 100% long (all stop-losses) from mixed phases
        if phase == Phase.RECOVER and windows.is_all_stop_losses():
            logger.info("RESET trigger: RECOVER → 100% long")
            return True
        
        if phase == Phase.RETRACEMENT and windows.is_all_stop_losses():
            logger.info("RESET trigger: RETRACEMENT → 100% long")
            return True
        
        return False
    
    def reset_for_new_cycle(self, new_position_value: Decimal, new_asset_size: Decimal):
        """
        Reset strategy for new cycle after RESET.
        
        Args:
            new_position_value: New position value after compound growth
            new_asset_size: New asset size after compound growth
        """
        # Update position state for new cycle
        self.position_state.update_for_reset(new_asset_size, new_position_value)
        
        # Reinitialize windows
        self._initialize_windows()
        
        logger.info(f"Strategy reset for cycle {self.position_state.cycle_number}")
        logger.info(f"Cumulative growth: {self.position_state.cumulative_growth:.2%}")
    
    def get_initial_orders(self) -> List[Tuple[int, OrderType]]:
        """
        Get initial orders to place when starting strategy.
        
        Returns:
            List of (unit, order_type) tuples
        """
        orders = []
        for unit in self.windows.stop_loss_orders:
            orders.append((unit, OrderType.STOP_LOSS_SELL))
        return orders
    
    def handle_order_fill(self, fill_event: OrderFillEvent) -> Optional[Tuple[int, OrderType]]:
        """
        Process an order fill and determine replacement.
        
        Args:
            fill_event: Order fill event details
            
        Returns:
            Replacement order details if needed
        """
        # Get replacement order
        replacement = self.get_replacement_order(
            fill_event.unit,
            fill_event.unit,  # Current unit approximated by fill unit
            fill_event.order_type
        )
        
        # Update phase after fill
        fill_event.phase_after = self.detect_phase()
        
        return replacement
    
    def get_window_summary(self) -> Dict:
        """
        Get current window and phase summary for monitoring.
        
        Returns:
            Dictionary with current strategy state
        """
        return {
            'phase': self.current_phase.value,
            'stop_loss_orders': self.windows.stop_loss_orders.copy(),
            'limit_buy_orders': self.windows.limit_buy_orders.copy(),
            'total_orders': self.windows.total_orders(),
            'is_mixed': self.windows.is_mixed(),
            'cycle_number': self.position_state.cycle_number,
            'cumulative_growth': float(self.position_state.cumulative_growth)
        }
    
    def validate_order_placement(self, order_type: OrderType, unit: int) -> bool:
        """
        Validate if an order placement is appropriate for current state.
        
        Args:
            order_type: Type of order to place
            unit: Unit level for order
            
        Returns:
            True if order is valid
        """
        # Check window constraints
        if self.windows.total_orders() >= 4:
            logger.warning(f"Cannot place order: already have 4 orders")
            return False
        
        # Validate order type for phase
        if self.current_phase == Phase.ADVANCE:
            if order_type != OrderType.STOP_LOSS_SELL:
                logger.warning(f"Invalid order type {order_type} for ADVANCE phase")
                return False
        
        elif self.current_phase == Phase.DECLINE:
            if order_type != OrderType.LIMIT_BUY:
                logger.warning(f"Invalid order type {order_type} for DECLINE phase")
                return False
        
        # Check for duplicate orders
        if order_type == OrderType.STOP_LOSS_SELL and unit in self.windows.stop_loss_orders:
            logger.warning(f"Stop-loss already exists at unit {unit}")
            return False
        
        if order_type == OrderType.LIMIT_BUY and unit in self.windows.limit_buy_orders:
            logger.warning(f"Limit buy already exists at unit {unit}")
            return False
        
        return True
    
    def get_missing_orders(self, current_unit: int) -> List[Tuple[int, OrderType]]:
        """
        Identify any missing orders that should be placed.
        Used for recovery after disconnection or errors.
        
        Args:
            current_unit: Current price unit
            
        Returns:
            List of (unit, order_type) that should be placed
        """
        missing = []
        
        if self.current_phase == Phase.ADVANCE:
            # Should have 4 stop-losses at [current-4, current-3, current-2, current-1]
            expected = [current_unit - i for i in range(4, 0, -1)]
            for unit in expected:
                if unit not in self.windows.stop_loss_orders:
                    missing.append((unit, OrderType.STOP_LOSS_SELL))
        
        elif self.current_phase == Phase.DECLINE:
            # Should have 4 limit buys at [current+1, current+2, current+3, current+4]
            expected = [current_unit + i for i in range(1, 5)]
            for unit in expected:
                if unit not in self.windows.limit_buy_orders:
                    missing.append((unit, OrderType.LIMIT_BUY))
        
        # Mixed phases are dynamic, harder to determine missing orders
        
        return missing