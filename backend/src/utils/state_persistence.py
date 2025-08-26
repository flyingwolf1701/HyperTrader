"""
Strategy state persistence for crash recovery
"""
import json
import pickle
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger


class StatePersistence:
    """Manages persistent storage of strategy state for recovery"""
    
    def __init__(self, state_dir: str = "state"):
        """Initialize state persistence manager"""
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        
        # State file paths
        self.active_state_file = self.state_dir / "active_strategy.json"
        self.backup_state_file = self.state_dir / "backup_strategy.json"
        
    def save_state(self, symbol: str, state_data: Dict[str, Any]):
        """
        Save strategy state to disk
        
        Args:
            symbol: Trading symbol
            state_data: Dictionary containing strategy state
        """
        try:
            # Backup existing state first
            if self.active_state_file.exists():
                import shutil
                shutil.copy(self.active_state_file, self.backup_state_file)
            
            # Prepare state for JSON serialization
            serializable_state = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "phase": state_data.get("phase", "UNKNOWN"),
                "position_size_usd": str(state_data.get("position_size_usd", 0)),
                "unit_size": str(state_data.get("unit_size", 2)),
                "leverage": state_data.get("leverage", 10),
                "entry_price": str(state_data.get("entry_price", 0)),
                "entry_time": state_data.get("entry_time"),
                "has_position": state_data.get("has_position", False),
                "position_allocation": str(state_data.get("position_allocation", 0)),
                "initial_position_allocation": str(state_data.get("initial_position_allocation", 0)),
                "position_fragment": str(state_data.get("position_fragment", 0)),
                "hedge_fragment": str(state_data.get("hedge_fragment", 0)),
                "reset_count": state_data.get("reset_count", 0),
                "pre_reset_value": str(state_data.get("pre_reset_value", 0)),
                "last_recovery_unit": state_data.get("last_recovery_unit", 0),
                "unit_tracker": {
                    "current_unit": state_data.get("current_unit", 0),
                    "peak_unit": state_data.get("peak_unit", 0),
                    "valley_unit": state_data.get("valley_unit", 0),
                }
            }
            
            # Save to file
            with open(self.active_state_file, 'w') as f:
                json.dump(serializable_state, f, indent=2)
            
            logger.debug(f"State saved for {symbol} in phase {serializable_state['phase']}")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Load strategy state from disk
        
        Returns:
            Dictionary containing strategy state or None if no state exists
        """
        try:
            if not self.active_state_file.exists():
                logger.info("No saved state found")
                return None
            
            with open(self.active_state_file, 'r') as f:
                saved_state = json.load(f)
            
            # Convert string decimals back to Decimal objects
            restored_state = {
                "timestamp": saved_state["timestamp"],
                "symbol": saved_state["symbol"],
                "phase": saved_state["phase"],
                "position_size_usd": Decimal(saved_state["position_size_usd"]),
                "unit_size": Decimal(saved_state["unit_size"]),
                "leverage": saved_state["leverage"],
                "entry_price": Decimal(saved_state["entry_price"]) if saved_state["entry_price"] != "0" else None,
                "entry_time": saved_state["entry_time"],
                "has_position": saved_state["has_position"],
                "position_allocation": Decimal(saved_state["position_allocation"]),
                "initial_position_allocation": Decimal(saved_state["initial_position_allocation"]),
                "position_fragment": Decimal(saved_state["position_fragment"]),
                "hedge_fragment": Decimal(saved_state["hedge_fragment"]),
                "reset_count": saved_state["reset_count"],
                "pre_reset_value": Decimal(saved_state["pre_reset_value"]),
                "last_recovery_unit": saved_state["last_recovery_unit"],
                "current_unit": saved_state["unit_tracker"]["current_unit"],
                "peak_unit": saved_state["unit_tracker"]["peak_unit"],
                "valley_unit": saved_state["unit_tracker"]["valley_unit"],
            }
            
            logger.info(f"Loaded saved state from {saved_state['timestamp']}")
            logger.info(f"  Symbol: {restored_state['symbol']}")
            logger.info(f"  Phase: {restored_state['phase']}")
            logger.info(f"  Position: ${restored_state['position_allocation']}")
            
            return restored_state
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            
            # Try backup
            if self.backup_state_file.exists():
                logger.info("Attempting to load backup state...")
                import shutil
                shutil.copy(self.backup_state_file, self.active_state_file)
                return self.load_state()  # Recursive call to load backup
            
            return None
    
    def clear_state(self):
        """Clear saved state files"""
        try:
            if self.active_state_file.exists():
                self.active_state_file.unlink()
                logger.info("Active state cleared")
            
            if self.backup_state_file.exists():
                self.backup_state_file.unlink()
                logger.info("Backup state cleared")
                
        except Exception as e:
            logger.error(f"Failed to clear state: {e}")
    
    def state_exists(self) -> bool:
        """Check if a saved state exists"""
        return self.active_state_file.exists()