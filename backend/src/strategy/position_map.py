"""
Position Map Management for HyperTrader
Manages position map for unit-based order tracking
Uses centralized data models
"""

from decimal import Decimal
from typing import Optional, Dict
from loguru import logger

# Import from centralized data models
from .data_models import (
    OrderType, ExecutionStatus, PositionState, PositionConfig
)


def calculate_initial_position_map(
    entry_price: Decimal, 
    unit_size_usd: Decimal,
    asset_size: Decimal,
    position_value_usd: Decimal,
    unit_range: int = 10
) -> tuple[PositionState, Dict[int, PositionConfig]]:
    """
    Calculate initial position map with per-unit configurations.
    
    Args:
        entry_price: Entry price for unit 0
        unit_size_usd: USD price movement per unit
        asset_size: The actual amount of asset we purchased
        position_value_usd: Total USD value of the position
        unit_range: How many units above/below to pre-calculate (default: 10)
        
    Returns:
        Tuple of (PositionState, Dict[unit -> PositionConfig])
    """
    # Validate inputs
    if unit_size_usd <= 0:
        raise ValueError(f"unit_size_usd must be positive, got {unit_size_usd}")
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    if asset_size <= 0:
        raise ValueError(f"asset_size must be positive, got {asset_size}")
    if position_value_usd <= 0:
        raise ValueError(f"position_value_usd must be positive, got {position_value_usd}")
    
    # Create static configuration (shared across all units)
    position_state = PositionState(
        entry_price=entry_price,
        unit_size_usd=unit_size_usd,
        asset_size=asset_size,
        position_value_usd=position_value_usd,
        original_asset_size=asset_size,    # Lock original size for consistent fragments
        original_position_value_usd=position_value_usd,  # Lock original value
        long_fragment_usd=Decimal("0"),    # Will be calculated in __post_init__
        long_fragment_asset=Decimal("0"),  # Will be calculated in __post_init__
    )
    
    # Create per-unit configurations
    position_map = {}
    for unit in range(-unit_range, unit_range + 1):  # -10 to +10 inclusive
        unit_price = position_state.get_price_for_unit(unit)
        position_map[unit] = PositionConfig(unit=unit, price=unit_price)
    
    logger.info(f"Position map created: Entry ${entry_price}, Unit size ${unit_size_usd}")
    logger.info(f"Fragments: {position_state.long_fragment_asset:.6f} asset, "
               f"${position_state.long_fragment_usd:.2f} USD")
    logger.info(f"Range: ${position_map[-unit_range].price:.2f} to ${position_map[unit_range].price:.2f}")
    
    return position_state, position_map


def add_unit_level(
    position_state: PositionState,
    position_map: Dict[int, PositionConfig],
    new_unit: int
) -> bool:
    """
    Add a new unit level to the position map (for new peaks or valleys).
    
    Args:
        position_state: Static position configuration
        position_map: Existing position map dictionary
        new_unit: The new unit number to add (positive for peaks, negative for valleys)
        
    Returns:
        True if successful, False if unit already exists
    """
    # Check if unit already exists
    if new_unit in position_map:
        logger.warning(f"Unit {new_unit} already exists in position map")
        return False
    
    # Calculate price for the new unit using position_state
    unit_price = position_state.get_price_for_unit(new_unit)
    
    # Create new position config for this unit
    new_config = PositionConfig(unit=new_unit, price=unit_price)
    
    # Add to position map
    position_map[new_unit] = new_config
    
    # Dynamic logging based on unit type
    unit_type = "PEAK" if new_unit > 0 else "VALLEY"
    logger.info(f"New {unit_type} unit added: Unit {new_unit} at ${unit_price:.2f}")
    return True


def get_active_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units with active orders"""
    return {unit: config for unit, config in position_map.items() if config.is_active}


def get_filled_orders(position_map: Dict[int, PositionConfig]) -> Dict[int, PositionConfig]:
    """Get all units that have been filled"""
    return {unit: config for unit, config in position_map.items()
            if config.execution_status == ExecutionStatus.FILLED}


def get_orders_by_type(position_map: Dict[int, PositionConfig], order_type: OrderType) -> Dict[int, PositionConfig]:
    """Get all units with a specific order type"""
    return {unit: config for unit, config in position_map.items() 
            if config.order_type == order_type and config.is_active}


def cancel_all_active_orders(position_map: Dict[int, PositionConfig]):
    """Cancel all active orders in the position map"""
    for unit, config in position_map.items():
        if config.is_active:
            config.mark_cancelled()
            logger.info(f"Cancelled order for unit {unit}")

