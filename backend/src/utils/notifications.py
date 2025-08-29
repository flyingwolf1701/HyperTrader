"""Notification manager for alerts and updates"""
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications for important events"""
    
    def __init__(self, enable_notifications: bool = True):
        self.enabled = enable_notifications
        self.notification_log = []
    
    def notify(self, title: str, message: str, level: str = "INFO"):
        """Send a notification"""
        if not self.enabled:
            return
        
        notification = {
            'timestamp': datetime.now().isoformat(),
            'title': title,
            'message': message,
            'level': level
        }
        
        self.notification_log.append(notification)
        
        # Log the notification
        if level == "ERROR":
            logger.error(f"🚨 {title}: {message}")
        elif level == "WARNING":
            logger.warning(f"⚠️ {title}: {message}")
        else:
            logger.info(f"ℹ️ {title}: {message}")
    
    def notify_phase_change(self, symbol: str, old_phase: str, new_phase: str):
        """Notify about phase changes"""
        self.notify(
            "Phase Change",
            f"{symbol}: {old_phase} → {new_phase}",
            "INFO"
        )
    
    def notify_reset(self, symbol: str, profit: float):
        """Notify about reset events"""
        emoji = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
        self.notify(
            "RESET Triggered",
            f"{symbol}: Cycle complete {emoji} ${profit:.2f}",
            "INFO"
        )
    
    def notify_error(self, error_type: str, details: str):
        """Notify about errors"""
        self.notify(
            f"Error: {error_type}",
            details,
            "ERROR"
        )
    
    def notify_connection(self, service: str, status: str):
        """Notify about connection status"""
        level = "INFO" if status == "connected" else "WARNING"
        self.notify(
            f"{service} Connection",
            f"Status: {status}",
            level
        )
    
    def get_recent_notifications(self, count: int = 10) -> list:
        """Get recent notifications"""
        return self.notification_log[-count:]