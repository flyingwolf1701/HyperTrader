"""State persistence for strategy recovery"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StatePersistence:
    """Handles saving and loading strategy state"""
    
    def __init__(self, state_dir: str = "state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, symbol: str, state: Dict[str, Any]):
        """Save strategy state to disk"""
        try:
            # Clean symbol for filename
            clean_symbol = symbol.replace('/', '_').replace(':', '_')
            state_file = self.state_dir / f"{clean_symbol}_state.json"
            
            # Add metadata
            state['_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'symbol': symbol,
                'version': '1.0'
            }
            
            # Convert Decimal and other types to JSON-serializable
            state_json = self._prepare_for_json(state)
            
            # Save to file
            with open(state_file, 'w') as f:
                json.dump(state_json, f, indent=2)
            
            logger.debug(f"State saved for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state for {symbol}: {e}")
            return False
    
    def load_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Load strategy state from disk"""
        try:
            clean_symbol = symbol.replace('/', '_').replace(':', '_')
            state_file = self.state_dir / f"{clean_symbol}_state.json"
            
            if not state_file.exists():
                logger.debug(f"No saved state found for {symbol}")
                return None
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            logger.info(f"State loaded for {symbol} (saved at {state.get('_metadata', {}).get('saved_at')})")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load state for {symbol}: {e}")
            return None
    
    def delete_state(self, symbol: str) -> bool:
        """Delete saved state"""
        try:
            clean_symbol = symbol.replace('/', '_').replace(':', '_')
            state_file = self.state_dir / f"{clean_symbol}_state.json"
            
            if state_file.exists():
                state_file.unlink()
                logger.info(f"State deleted for {symbol}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete state for {symbol}: {e}")
            return False
    
    def list_saved_states(self) -> list:
        """List all saved states"""
        states = []
        for state_file in self.state_dir.glob("*_state.json"):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    metadata = state.get('_metadata', {})
                    states.append({
                        'symbol': metadata.get('symbol'),
                        'saved_at': metadata.get('saved_at'),
                        'file': str(state_file)
                    })
            except:
                continue
        return states
    
    def _prepare_for_json(self, obj: Any) -> Any:
        """Convert non-JSON-serializable types"""
        if isinstance(obj, dict):
            return {k: self._prepare_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._prepare_for_json(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._prepare_for_json(obj.__dict__)
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            try:
                return float(obj)
            except:
                return str(obj)