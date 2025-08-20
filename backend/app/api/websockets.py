"""WebSocket endpoints for real-time communication."""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    """WebSocket connection manager."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific connection."""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connections."""
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# TODO: Implement WebSocket endpoint handlers
