from decimal import Decimal
import pytest
from hypothesis import given, strategies as st

# Assuming the project structure is now backend/src and backend/tests
from src.strategy.unit_tracker import UnitTracker

# --- 1. Table-Driven Tests (Inspired by the video's tables) ---

# We define a set of test cases in a list, just like a table.
# Each tuple is a row: (current_price, unit_index, expected_price)
UNIT_TO_PRICE_TABLE = [
    # Test cases around a base price of 100
    (Decimal("100"), 0, Decimal("100.0000")),
    (Decimal("100"), 1, Decimal("101.0000")),  # 100 * (1 + 0.01)
    (Decimal("100"), -1, Decimal("99.0100")), # 100 / (1 + 0.01)
    (Decimal("100"), 2, Decimal("102.0100")),  # 100 * (1 + 0.01)^2
    (Decimal("100"), -2, Decimal("98.0297")), # 100 / (1 + 0.01)^2
    # Test cases with a different base price
    (Decimal("150"), 0, Decimal("150.0000")),
    (Decimal("150"), 5, Decimal("157.6515")), # 150 * (1.01)^5
    (Decimal("150"), -5, Decimal("142.7201")),# 150 / (1.01)^5
]

@pytest.mark.parametrize("current_price, unit_index, expected_price", UNIT_TO_PRICE_TABLE)
def test_unit_to_price_from_table(current_price, unit_index, expected_price):
    """
    Tests the unit_to_price calculation against a predefined table of examples.
    This is the pytest equivalent of the visual table from the video.
    """
    tracker = UnitTracker(grid_spacing=Decimal("0.01"), target_units=100)
    tracker.current_price = current_price
    # Set the center of the grid for calculation purposes
    tracker.units_held = tracker.price_to_unit(current_price) 
    
    calculated_price = tracker.unit_to_price(unit_index + tracker.units_held)
    
    # Assert that the calculation is correct within a tolerance
    assert abs(calculated_price - expected_price) < Decimal("0.0001")

# --- 2. Property-Based Tests (Inspired by Hypothesis) ---

@st.composite
def unit_tracker_and_price(draw):
    """A Hypothesis strategy to generate a UnitTracker and a random price."""
    grid_spacing = draw(st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.1"), places=4))
    target_units = draw(st.integers(min_value=10, max_value=200))
    current_price = draw(st.decimals(min_value=Decimal("10"), max_value=Decimal("10000"), places=4))
    
    tracker = UnitTracker(grid_spacing=grid_spacing, target_units=target_units)
    tracker.current_price = current_price
    return tracker, current_price

@given(data=unit_tracker_and_price())
def test_property_price_to_unit_is_inverse_of_unit_to_price(data):
    """
    Property: Applying price_to_unit and then unit_to_price should return
    the original price (or very close to it).
    """
    tracker, price = data
    unit = tracker.price_to_unit(price)
    recalculated_price = tracker.unit_to_price(unit)

    # The price should be consistent within a small fraction of the grid spacing
    assert abs(recalculated_price - price) <= tracker.grid_spacing * Decimal("0.01")

@given(tracker=st.builds(UnitTracker,
                        grid_spacing=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.1"), places=4),
                        target_units=st.integers(min_value=10, max_value=200)),
       unit=st.integers(min_value=-50, max_value=50))
def test_property_unit_to_price_is_monotonic(tracker, unit):
    """
    Property: For any unit `n`, the price at `n` must be less than the price at `n+1`.
    The price grid should always be increasing.
    """
    price_n = tracker.unit_to_price(unit)
    price_n_plus_1 = tracker.unit_to_price(unit + 1)
    assert price_n < price_n_plus_1
