"""
Configuration Loaders for LLMCycle
==================================
Allows automatic discovery of provider configurations (API keys, Base URLs)
from various sources like Environment Variables or Redis, using customizable
prefixes, suffixes, and patterns.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
import os


class ConfigLoader(ABC):
    """Abstract base class for configuration loaders."""
    def __init__(self, prefix: str = "", suffix: str = "_API_KEYS"):
        self.prefix = prefix
        self.suffix = suffix

    @abstractmethod
    def load_configs(self) -> Dict[str, Dict[str, str]]:
        """
        Scan the source and return discovered configurations.
        Returns:
            { "provider_name": {"api_keys": "sk-1,sk-2", "base_url": "https..."} }
        """
        pass

    def _parse_provider_from_key(self, key: str) -> Optional[str]:
        if self.prefix and not key.startswith(self.prefix):
            return None
        if self.suffix and not key.endswith(self.suffix):
            return None
        
        provider = key
        if self.prefix:
            provider = provider[len(self.prefix):]
        if self.suffix:
            provider = provider[:-len(self.suffix)]
        return provider.upper()


class EnvConfigLoader(ConfigLoader):
    """Loads provider configs from environment variables."""
    def load_configs(self) -> Dict[str, Dict[str, str]]:
        configs = {}
        for env_key, env_val in os.environ.items():
            provider = self._parse_provider_from_key(env_key)
            if provider:
                if provider not in configs:
                    configs[provider] = {}
                configs[provider]["api_keys"] = env_val
                
                # Try to find base_url
                base_url_key = f"{self.prefix}{provider}_BASE_URL"
                if base_url_key in os.environ:
                    configs[provider]["base_url"] = os.environ[base_url_key]
        return configs


class RedisConfigLoader(ConfigLoader):
    """Loads provider configs from a Redis database."""
    def __init__(self, redis_url: str = "", prefix: str = "", suffix: str = "_API_KEYS", driver=None):
        super().__init__(prefix, suffix)
        self.redis_url = redis_url
        self.driver = driver
        self._client = None
        
    def _get_client(self):
        if self.driver:
            return self.driver.get_sync_client()
            
        if self._client is None:
            if not self.redis_url:
                raise ValueError("redis_url or driver must be provided to RedisConfigLoader")
            try:
                import redis
            except ImportError as e:
                raise ImportError(
                    "RedisConfigLoader requires redis. Install with: pip install redis"
                ) from e
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client
        
    def load_configs(self) -> Dict[str, Dict[str, str]]:
        client = self._get_client()
        configs = {}
        
        # Pattern to scan
        scan_pattern = f"{self.prefix}*{self.suffix}"
        cursor = '0'
        while cursor != 0:
            cursor, keys = client.scan(cursor=cursor, match=scan_pattern, count=100)
            for key in keys:
                provider = self._parse_provider_from_key(key)
                if provider:
                    if provider not in configs:
                        configs[provider] = {}
                    configs[provider]["api_keys"] = client.get(key)
                    
                    # Try to find base_url
                    base_url_key = f"{self.prefix}{provider}_BASE_URL"
                    base_url_val = client.get(base_url_key)
                    if base_url_val:
                        configs[provider]["base_url"] = base_url_val
        return configs
