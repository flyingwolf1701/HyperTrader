"""
Notification system for HyperTrader phase transitions and important events
"""
import os
from decimal import Decimal
from datetime import datetime
from typing import Optional
from loguru import logger


class NotificationManager:
    """Manages notifications for strategy events"""
    
    def __init__(self):
        """Initialize notification manager"""
        self.enabled = True
        self.sound_enabled = os.name == 'nt'  # Enable sound on Windows
        
    def notify_phase_change(
        self,
        from_phase: str,
        to_phase: str,
        symbol: str,
        current_price: Decimal,
        position_value: Optional[Decimal] = None
    ):
        """Send notification for phase change"""
        
        # Create message
        message = f"""
=====================================
PHASE TRANSITION ALERT
=====================================
Symbol: {symbol}
Time: {datetime.now().strftime('%H:%M:%S')}
Transition: {from_phase} → {to_phase}
Current Price: ${current_price:.2f}
"""
        if position_value:
            message += f"Position Value: ${position_value:.2f}\n"
        
        message += "====================================="
        
        # Log prominently
        logger.warning(message)
        
        # System beep on Windows
        if self.sound_enabled:
            try:
                import winsound
                # Different beep patterns for different phases
                if to_phase == "RETRACEMENT":
                    winsound.Beep(800, 300)  # Lower pitch warning
                elif to_phase == "DECLINE":
                    winsound.Beep(600, 500)  # Longer, lower pitch
                elif to_phase == "RECOVERY":
                    winsound.Beep(1000, 200)  # Higher pitch, short
                    winsound.Beep(1200, 200)  # Double beep for recovery
                elif to_phase == "ADVANCE":
                    winsound.Beep(1200, 300)  # High pitch for advance
            except:
                pass
    
    def notify_trade_execution(
        self,
        action: str,
        symbol: str,
        amount: Decimal,
        price: Decimal,
        reason: str
    ):
        """Send notification for trade execution"""
        
        message = f"""
-------------------------------------
TRADE EXECUTED
-------------------------------------
Action: {action.upper()}
Symbol: {symbol}
Amount: {amount:.4f}
Price: ${price:.2f}
Value: ${(amount * price):.2f}
Reason: {reason}
Time: {datetime.now().strftime('%H:%M:%S')}
-------------------------------------
"""
        
        logger.info(message)
        
        # Quick beep for trades
        if self.sound_enabled:
            try:
                import winsound
                winsound.Beep(900, 150)
            except:
                pass
    
    def notify_reset(
        self,
        reset_count: int,
        old_value: Decimal,
        new_value: Decimal,
        profit: Decimal
    ):
        """Send notification for RESET event"""
        
        message = f"""
*************************************
RESET TRIGGERED
*************************************
Reset #: {reset_count}
Profit Locked: ${profit:.2f}
Old Position: ${old_value:.2f}
New Position: ${new_value:.2f}
Time: {datetime.now().strftime('%H:%M:%S')}
*************************************
"""
        
        logger.success(message)
        
        # Victory sound for reset
        if self.sound_enabled:
            try:
                import winsound
                # Play ascending notes
                winsound.Beep(800, 200)
                winsound.Beep(1000, 200)
                winsound.Beep(1200, 300)
            except:
                pass
    
    def notify_error(self, error_msg: str):
        """Send error notification"""
        
        message = f"""
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ERROR ALERT
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
{error_msg}
Time: {datetime.now().strftime('%H:%M:%S')}
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""
        
        logger.error(message)
        
        # Error sound
        if self.sound_enabled:
            try:
                import winsound
                # Low pitched error sound
                winsound.Beep(400, 1000)
            except:
                pass
    
    def notify_status(self, message: str):
        """Send general status notification"""
        logger.info(f"\n[STATUS] {message}\n")