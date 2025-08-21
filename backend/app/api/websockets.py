# backend/app/api/websockets.py

import logging
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.state import system_state

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection and adds it to the list."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection from the list."""
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        """Sends a message to all connected clients."""
        for connection in self.active_connections:
            await connection.send_text(message)

# Create a single manager instance to be used across the application
websocket_manager = ConnectionManager()
router = APIRouter()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """
    Handles WebSocket connections from frontend clients.
    """
    await websocket_manager.connect(websocket)
    
    # Send the current system state immediately upon connection
    try:
        await websocket.send_text(system_state.model_dump_json())
    except Exception as e:
        logger.error(f"Error sending initial state to client {client_id}: {e}")

    try:
        # Keep the connection alive and listen for messages
        while True:
            # This loop keeps the connection open.
            # You could add logic here to handle messages from the client if needed.
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
