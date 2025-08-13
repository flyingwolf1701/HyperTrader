"""API endpoints for portfolio management."""

from fastapi import APIRouter

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/")
async def get_portfolio():
    """Get current portfolio allocation."""
    return {"message": "Portfolio endpoint - coming soon"}


@router.put("/allocation")
async def update_allocation():
    """Update portfolio allocation."""
    return {"message": "Update allocation - coming soon"}


@router.get("/balance")
async def get_balance():
    """Get portfolio balance and cash reserves."""
    return {"message": "Portfolio balance - coming soon"}


@router.post("/rebalance")
async def rebalance_portfolio():
    """Trigger portfolio rebalancing."""
    return {"message": "Rebalance portfolio - coming soon"}
