"""API endpoints for trading plans management."""

from fastapi import APIRouter

router = APIRouter(prefix="/trading-plans", tags=["trading-plans"])


@router.get("/")
async def get_trading_plans():
    """Get all trading plans."""
    return {"message": "Trading plans endpoint - coming soon"}


@router.post("/")
async def create_trading_plan():
    """Create a new trading plan."""
    return {"message": "Create trading plan - coming soon"}


@router.get("/{plan_id}")
async def get_trading_plan(plan_id: int):
    """Get a specific trading plan."""
    return {"message": f"Trading plan {plan_id} - coming soon"}


@router.put("/{plan_id}")
async def update_trading_plan(plan_id: int):
    """Update a trading plan."""
    return {"message": f"Update trading plan {plan_id} - coming soon"}


@router.delete("/{plan_id}")
async def delete_trading_plan(plan_id: int):
    """Delete a trading plan."""
    return {"message": f"Delete trading plan {plan_id} - coming soon"}
