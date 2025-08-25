"""
Persistent trade logging system for HyperTrader
"""
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger


class TradeLogger:
    """Persistent logger for tracking all trades and strategy events"""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize trade logger with persistent storage"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create daily log file
        today = datetime.now().strftime("%Y%m%d")
        self.trade_file = self.log_dir / f"trades_{today}.json"
        self.event_file = self.log_dir / f"events_{today}.json"
        
        # Load existing logs
        self.trades = self._load_json(self.trade_file)
        self.events = self._load_json(self.event_file)
        
        # Session tracking
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"Trade logger initialized - Session: {self.session_id}")
    
    def _load_json(self, file_path: Path) -> list:
        """Load existing JSON log file"""
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_json(self, data: list, file_path: Path):
        """Save data to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def log_trade(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        order_type: str,
        phase: str,
        reason: str,
        order_id: Optional[str] = None,
        pnl: Optional[Decimal] = None
    ):
        """Log a trade execution"""
        trade = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "symbol": symbol,
            "side": side,
            "amount": float(amount),
            "price": float(price),
            "order_type": order_type,
            "phase": phase,
            "reason": reason,
            "order_id": order_id,
            "pnl": float(pnl) if pnl else None,
            "value_usd": float(amount * price)
        }
        
        self.trades.append(trade)
        self._save_json(self.trades, self.trade_file)
        
        logger.info(
            f"Trade logged: {side.upper()} {amount:.4f} @ ${price:.2f} "
            f"(Phase: {phase}, Reason: {reason})"
        )
        
        return trade
    
    def log_event(
        self,
        event_type: str,
        phase: str,
        details: Dict[str, Any]
    ):
        """Log a strategy event (phase change, reset, etc)"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "phase": phase,
            "details": {k: str(v) if isinstance(v, Decimal) else v 
                      for k, v in details.items()}
        }
        
        self.events.append(event)
        self._save_json(self.events, self.event_file)
        
        logger.info(f"Event logged: {event_type} in {phase}")
        
        return event
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session"""
        session_trades = [t for t in self.trades if t['session_id'] == self.session_id]
        
        if not session_trades:
            return {
                "session_id": self.session_id,
                "total_trades": 0,
                "total_volume": 0,
                "realized_pnl": 0
            }
        
        total_volume = sum(t['value_usd'] for t in session_trades)
        realized_pnl = sum(t.get('pnl', 0) for t in session_trades if t.get('pnl'))
        
        return {
            "session_id": self.session_id,
            "start_time": session_trades[0]['timestamp'],
            "last_trade": session_trades[-1]['timestamp'],
            "total_trades": len(session_trades),
            "total_volume": total_volume,
            "realized_pnl": realized_pnl,
            "trades_by_phase": self._count_by_phase(session_trades)
        }
    
    def _count_by_phase(self, trades: list) -> Dict[str, int]:
        """Count trades by phase"""
        counts = {}
        for trade in trades:
            phase = trade.get('phase', 'UNKNOWN')
            counts[phase] = counts.get(phase, 0) + 1
        return counts
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get summary of all trades today"""
        if not self.trades:
            return {"total_trades": 0, "total_volume": 0}
        
        total_volume = sum(t['value_usd'] for t in self.trades)
        realized_pnl = sum(t.get('pnl', 0) for t in self.trades if t.get('pnl'))
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": len(self.trades),
            "total_volume": total_volume,
            "realized_pnl": realized_pnl,
            "unique_sessions": len(set(t['session_id'] for t in self.trades)),
            "trades_by_phase": self._count_by_phase(self.trades)
        }