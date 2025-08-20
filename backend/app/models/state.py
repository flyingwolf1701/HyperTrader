from pydantic import BaseModel, Field, validator
from decimal import Decimal
from typing import Optional, Literal
from datetime import datetime


PhaseType = Literal["advance", "retracement", "decline", "recovery"]


class SystemState(BaseModel):
    """
    Core SystemState model that holds all information about a single trading plan.
    All financial fields use high-precision Decimal type for accurate calculations.
    """
    
    # Basic Trading Information
    symbol: str = Field(..., description="Trading pair, e.g., 'BTC/USDT'")
    current_phase: PhaseType = Field(default="advance", description="Current trading phase")
    
    # Price and Unit Information
    entry_price: Decimal = Field(..., description="Initial average fill price")
    unit_value: Decimal = Field(..., description="Dollar value of one unit of price movement")
    peak_price: Optional[Decimal] = Field(None, description="Highest price reached since last reset")
    valley_price: Optional[Decimal] = Field(None, description="Lowest price reached since last reset")
    
    # Unit Tracking
    current_unit: int = Field(default=0, description="Current unit relative to entry price")
    peak_unit: Optional[int] = Field(None, description="Highest unit reached")
    valley_unit: Optional[int] = Field(None, description="Lowest unit reached")
    
    # Allocation Amounts (all in dollars)
    long_invested: Decimal = Field(default=Decimal("0"), description="Dollar amount in long positions")
    long_cash: Decimal = Field(default=Decimal("0"), description="Dollar amount held as cash")
    hedge_long: Decimal = Field(default=Decimal("0"), description="Dollar amount in hedge long positions")
    hedge_short: Decimal = Field(default=Decimal("0"), description="Dollar amount in hedge short positions")
    
    # System Information
    initial_margin: Decimal = Field(..., description="Total margin used to enter the trade")
    leverage: int = Field(default=1, description="Leverage used for the trade")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the trade was started")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Performance Tracking
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized profit/loss")
    unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Unrealized profit/loss")
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            Decimal: str  # Serialize Decimal as string for JSON compatibility
        }
        validate_assignment = True  # Validate on assignment
        use_enum_values = True
    
    @validator('entry_price', 'unit_value', 'initial_margin')
    def validate_positive_required_fields(cls, v):
        """Ensure critical financial fields are positive"""
        if v <= 0:
            raise ValueError("Must be positive")
        return v
    
    @validator('peak_price', 'valley_price', pre=True)
    def validate_optional_prices(cls, v):
        """Validate optional price fields"""
        if v is not None and v <= 0:
            raise ValueError("Price must be positive when provided")
        return v
    
    @validator('long_invested', 'long_cash', 'hedge_long', 'hedge_short', 'realized_pnl', 'unrealized_pnl')
    def validate_financial_fields(cls, v):
        """Ensure financial fields are valid decimals (can be negative for PnL)"""
        return Decimal(str(v)) if v is not None else Decimal("0")
    
    @validator('leverage')
    def validate_leverage(cls, v):
        """Ensure leverage is positive integer"""
        if v <= 0:
            raise ValueError("Leverage must be positive")
        return v
    
    @validator('updated_at', always=True)
    def set_updated_at(cls, v):
        """Always update the timestamp when model is modified"""
        return datetime.utcnow()
    
    def get_total_portfolio_value(self) -> Decimal:
        """Calculate total portfolio value"""
        return self.long_invested + self.long_cash + self.hedge_long + self.hedge_short
    
    def get_long_allocation_percent(self) -> Decimal:
        """Get long allocation percentage (invested / total long allocation)"""
        total_long = self.long_invested + self.long_cash
        if total_long == 0:
            return Decimal("0")
        return (self.long_invested / total_long) * 100
    
    def get_hedge_allocation_percent(self) -> Decimal:
        """Get hedge allocation percentage (long / total hedge allocation)"""
        total_hedge = self.hedge_long + abs(self.hedge_short)
        if total_hedge == 0:
            return Decimal("0")
        return (self.hedge_long / total_hedge) * 100
    
    def is_reset_condition_met(self) -> bool:
        """Check if system reset conditions are met"""
        return self.hedge_short == 0 and self.long_cash == 0
    
    def is_choppy_trading_active(self) -> bool:
        """Check if choppy trading detection is active"""
        total_long = self.long_invested + self.long_cash
        total_hedge = self.hedge_long + abs(self.hedge_short)
        
        # Long allocation partially allocated
        long_partial = 0 < self.long_invested < total_long
        
        # Hedge allocation partially allocated (has both long and short)
        hedge_partial = self.hedge_long > 0 and self.hedge_short > 0
        
        return long_partial or hedge_partial


class TradingPlanCreate(BaseModel):
    """Schema for creating a new trading plan"""
    symbol: str
    initial_margin: Decimal
    leverage: int = 1
    
    @validator('initial_margin')
    def validate_margin(cls, v):
        if v <= 0:
            raise ValueError("Initial margin must be positive")
        return v


class TradingPlanUpdate(BaseModel):
    """Schema for updating a trading plan"""
    current_phase: Optional[PhaseType] = None
    peak_price: Optional[Decimal] = None
    valley_price: Optional[Decimal] = None
    current_unit: Optional[int] = None
    peak_unit: Optional[int] = None
    valley_unit: Optional[int] = None
    long_invested: Optional[Decimal] = None
    long_cash: Optional[Decimal] = None
    hedge_long: Optional[Decimal] = None
    hedge_short: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None