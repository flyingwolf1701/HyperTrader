"""Trade logging utility"""
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class TradeLogger:
    """Logs trade activities to file and console"""
    
    def __init__(self, log_dir: str = "logs/trades"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
    def log_trade(self, trade_type: str, details: Dict[str, Any]):
        """Log a trade event"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'type': trade_type,
            'details': details
        }
        
        # Log to file
        with open(self.log_file, 'a') as f:
            f.write(f"{timestamp} | {trade_type} | {details}\n")
        
        # Log to console
        logger.info(f"Trade: {trade_type} - {details}")
        
        return log_entry
    
    def log_position_change(self, symbol: str, old_position: Any, new_position: Any):
        """Log position changes"""
        self.log_trade('POSITION_CHANGE', {
            'symbol': symbol,
            'old': str(old_position),
            'new': str(new_position)
        })
    
    def log_phase_change(self, symbol: str, old_phase: str, new_phase: str):
        """Log phase transitions"""
        self.log_trade('PHASE_CHANGE', {
            'symbol': symbol,
            'old_phase': old_phase,
            'new_phase': new_phase
        })
    
    def log_order(self, order_type: str, symbol: str, amount: float, price: float = None):
        """Log order execution"""
        details = {
            'symbol': symbol,
            'amount': amount
        }
        if price:
            details['price'] = price
        
        self.log_trade(f'ORDER_{order_type.upper()}', details)