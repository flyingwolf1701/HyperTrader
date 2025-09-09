"""
Function Descriptions for Fixed Position Map Data Structure
===========================================================

This document catalogs all functions and methods from the actual
"Fixed Position Map Data Structure.txt" file with detailed docstrings
describing their purpose, arguments, and return values.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

#=============================================================================
# backend\src\strategy\position_map_fixed.py
#=============================================================================

# ============================================================================
# ENUMS
# ============================================================================

class OrderType(Enum):
    """
    Types of orders that can be placed.
    
    Enumeration defining the four types of limit orders used in the strategy
    for both long and short position management.
    """
    LIMIT_SELL = "limit_sell"
    LIMIT_BUY = "limit_buy" 
    LIMIT_SHORT = "limit_short"
    LIMIT_COVER = "limit_cover"


class ExecutionStatus(Enum):
    """
    Order execution status.
    
    Tracks the lifecycle state of orders from placement through completion
    or cancellation.
    """
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ============================================================================
# DATA CLASSES AND THEIR METHODS
# ============================================================================

@dataclass 
class PositionState:
    """
    Static configuration that remains the same for the entire strategy cycle.
    These values are set once at position entry and don't change.
    
    Attributes:
        entry_price (Decimal): The average price we paid for our asset (unit 0)
        unit_size_usd (Decimal): USD price movement per unit ($5, $25, etc.)
        asset_size (Decimal): Total amount of asset we purchased
        position_value_usd (Decimal): Total USD value of the position at entry
        long_fragment_usd (Decimal): 25% of position value in USD (for buying)
        long_fragment_asset (Decimal): 25% of asset_size (for selling)
        short_fragment_usd (Decimal): 25% of position value in USD (for shorting)
        short_fragment_asset (Decimal): 25% of short position asset amount
    """

    def __post_init__(self):
        """
        Calculate standard fragments after initialization.
        
        Automatically computes 25% fragment values for long operations based on
        original position. Short fragments start with same USD value but will
        be updated during strategy execution.
        
        Args:
            None (uses instance attributes)
            
        Returns:
            None (modifies instance attributes in-place)
        """
        pass

    def get_price_for_unit(self, unit: int) -> Decimal:
        """
        Calculate price for any unit level.
        
        Uses entry price and unit size to determine the exact price that
        corresponds to a given unit number.
        
        Args:
            unit (int): Unit level (negative for below entry, positive for above)
            
        Returns:
            Decimal: Price for the specified unit level
            
        Example:
            entry_price=$4500, unit_size=$25, unit=-1 returns $4475
        """
        pass
    
    def update_short_fragments(self, total_short_position_value: Decimal, 
                             total_short_asset_size: Decimal):
        """
        Update short fragment values based on current short position.
        
        Called when short positions are established to recalculate fragment
        sizes based on actual short position value and size.
        
        Args:
            total_short_position_value (Decimal): Current USD value of short positions
            total_short_asset_size (Decimal): Total asset amount in shorts
            
        Returns:
            None (modifies instance attributes)
        """
        pass


@dataclass
class PositionConfig:
    """
    Dynamic state per unit level - tracks orders, execution, and real-time state.
    Each unit level gets its own PositionConfig instance.
    
    Attributes:
        unit (int): The unit level number
        price (Decimal): Price for this unit level
        order_id (Optional[str]): Active order ID (None if no active order)
        order_type (Optional[OrderType]): Type of active order
        execution_status (ExecutionStatus): Current execution status
        is_active (bool): Whether this unit has an active order
        executed_at (Optional[datetime]): When order was executed
        executed_price (Optional[Decimal]): Actual execution price
        executed_size (Optional[Decimal]): Actual execution size
        created_at (datetime): When this config was created
    """
    
    def __post_init__(self):
        """
        Initialize creation timestamp if not provided.
        
        Sets created_at to current time if it wasn't explicitly provided
        during instantiation.
        
        Args:
            None
            
        Returns:
            None (sets created_at attribute)
        """
        pass
    
    def mark_filled(self, executed_price: Decimal, executed_size: Decimal):
        """
        Mark this unit as filled with execution details.
        
        Updates the unit's state to reflect successful order execution,
        recording execution details and printing confirmation.
        
        Args:
            executed_price (Decimal): Price at which order was executed
            executed_size (Decimal): Amount that was executed
            
        Returns:
            None (updates instance state and prints confirmation)
        """
        pass
    
    def mark_cancelled(self):
        """
        Mark this unit's order as cancelled.
        
        Cleans up order tracking fields and sets status to cancelled.
        Used when orders are cancelled manually or automatically.
        
        Args:
            None
            
        Returns:
            None (updates instance state)
        """
        pass
    
    def set_active_order(self, order_id: str, order_type: OrderType):
        """
        Set an active order for this unit.
        
        Records the details of a newly placed order at this unit level.
        
        Args:
            order_id (str): Exchange-provided order identifier
            order_type (OrderType): Type of order being placed
            
        Returns:
            None (updates instance state)
        """
        pass


# ============================================================================
# STANDALONE FUNCTIONS
# ============================================================================

def calculate_initial_position_map(
    entry_price: Decimal, 
    unit_size_usd: Decimal,
    asset_size: Decimal,
    position_value_usd: Decimal,
    unit_range: int = 10
) -> tuple[PositionState, Dict[int, PositionConfig]]:
    """
    Calculate initial position map with per-unit configurations.
    
    Creates the complete position tracking structure including static
    configuration and per-unit dynamic tracking for a specified range
    of units above and below the entry price.
    
    Args:
        entry_price (Decimal): Entry price for unit 0
        unit_size_usd (Decimal): USD price movement per unit
        asset_size (Decimal): The actual amount of asset we purchased
        position_value_usd (Decimal): Total USD value of the position
        unit_range (int): How many units above/below to pre-calculate (default: 10)
        
    Returns:
        tuple[PositionState, Dict[int, PositionConfig]]: 
            - PositionState with calculated fragments
            - Dictionary mapping unit numbers to PositionConfig objects
            
    Side Effects:
        Prints position map creation summary with entry price, fragments, and range
    """
    pass


def add_unit_level(
    position_state: PositionState,
    position_map: Dict[int, PositionConfig],
    new_unit: int
) -> bool:
    """
    Add a new unit level to the position map (for new peaks or valleys).
    
    Extends the position map when price reaches levels beyond the initially
    calculated range. Used for tracking new peaks during advance phase or
    new valleys during decline phase.
    
    Args:
        position_state (PositionState): Static position configuration
        position_map (Dict[int, PositionConfig]): Existing position map dictionary
        new_unit (int): The new unit number to add (positive for peaks, negative for valleys)
        
    Returns:
        bool: True if successful, False if unit already exists
        
    Side Effects:
        - Adds new PositionConfig to position_map
        - Prints confirmation with unit type (PEAK/VALLEY) and price
    """
    pass


def get_active_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """
    Get all units with active orders.
    
    Filters the position map to return only units that currently have
    pending orders on the exchange.
    
    Args:
        position_map (Dict[int, PositionConfig]): Complete position map
        
    Returns:
        Dict[int, PositionConfig]: Subset containing only units with is_active=True
    """
    pass


def get_filled_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """
    Get all units that have been filled.
    
    Filters the position map to return only units where orders have been
    successfully executed by the exchange.
    
    Args:
        position_map (Dict[int, PositionConfig]): Complete position map
        
    Returns:
        Dict[int, PositionConfig]: Subset containing only units with FILLED status
    """
    pass


def cancel_all_active_orders(position_map: Dict[int, PositionConfig]):
    """
    Cancel all active orders in the position map.
    
    Iterates through all units and cancels any that have active orders.
    Used for emergency stops or phase transitions requiring clean slate.
    
    Args:
        position_map (Dict[int, PositionConfig]): Position map to process
        
    Returns:
        None
        
    Side Effects:
        - Calls mark_cancelled() on all active units
        - Prints cancellation confirmation for each cancelled order
        
    Note:
        This only updates internal state. Actual exchange API calls to cancel
        orders must be handled separately.
    """
    pass