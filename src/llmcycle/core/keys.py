import time
from typing import Dict, List, Optional
from llmcycle.schema import APIKeyStats

class KeyManager:
    """Handles multi-key rotation and rate-limit tracking."""
    
    def __init__(self):
        # provider -> list of API keys
        self._keys: Dict[str, List[str]] = {}
        # key -> stats
        self._stats: Dict[str, APIKeyStats] = {}
        # current index for round-robin
        self._indexes: Dict[str, int] = {}
        
    def add_key(self, provider: str, key: str):
        if provider not in self._keys:
            self._keys[provider] = []
            self._indexes[provider] = 0
            
        if key not in self._keys[provider]:
            self._keys[provider].append(key)
            self._stats[key] = APIKeyStats(key_hash=hash(key).__str__())

    def get_next_key(self, provider: str) -> Optional[str]:
        """Round-robin rotation strategy."""
        if provider not in self._keys or not self._keys[provider]:
            return None
            
        keys = self._keys[provider]
        index = self._indexes[provider]
        
        # Try to find an active key
        start_index = index
        while True:
            key = keys[index]
            stats = self._stats[key]
            
            if stats.is_active and stats.rate_limit_remaining > 0:
                stats.last_used = time.time()
                self._indexes[provider] = (index + 1) % len(keys)
                return key
                
            index = (index + 1) % len(keys)
            if index == start_index:
                # No active keys found
                return None
                
    def report_error(self, key: str, error_type: str):
        """Mark key as rate-limited or inactive based on error."""
        if key in self._stats:
            if error_type == "rate_limit":
                self._stats[key].rate_limit_remaining = 0
            elif error_type == "invalid_key":
                self._stats[key].is_active = False
