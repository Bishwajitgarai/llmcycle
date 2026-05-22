import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RouterStrategy(ABC):
    """Abstract strategy for sorting and selecting models."""
    
    @abstractmethod
    def sort_models(self, requested_model: str) -> List[str]:
        """Return a sorted list of fallback models."""
        pass

class FallbackRouter(RouterStrategy):
    """A simple router that uses a pre-defined fallback list."""
    
    def __init__(self, fallbacks: Dict[str, List[str]]):
        # e.g. {"gpt-4": ["gpt-4-turbo", "gpt-3.5-turbo"]}
        self.fallbacks = fallbacks
        
    def sort_models(self, requested_model: str) -> List[str]:
        # Always try the requested model first, then the fallbacks
        models = [requested_model]
        if requested_model in self.fallbacks:
            models.extend(self.fallbacks[requested_model])
        return models

class ModelRouter:
    """Main router class that manages strategies and routes requests."""
    
    def __init__(self, strategy: RouterStrategy):
        self.strategy = strategy
        
    def get_route(self, requested_model: str) -> List[str]:
        """Get ordered list of models to try."""
        return self.strategy.sort_models(requested_model)
