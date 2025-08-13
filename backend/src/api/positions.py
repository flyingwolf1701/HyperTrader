"""API endpoints for position monitoring."""

from fastapi import APIRouter

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/")
async def get_positions():
    """Get all active positions."""
    return {"message": "Positions endpoint - coming soon"}


@router.get("/{position_id}")
async def get_position(position_id: int):
    """Get specific position details."""
    return {"message": f"Position {position_id} - coming soon"}


@router.post("/{position_id}/hedge")
async def execute_hedge(position_id: int):
    """Execute hedge on position (manual trigger)."""
    return {"message": f"Execute hedge on position {position_id} - coming soon"}


@router.put("/{position_id}/stop-loss")
async def update_stop_loss(position_id: int):
    """Update stop loss for position."""
    return {"message": f"Update stop loss for position {position_id} - coming soon"}
