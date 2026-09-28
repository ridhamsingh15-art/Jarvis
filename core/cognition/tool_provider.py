import logging
from typing import List
from core.registry import Registry
from core.cognition.context_models import ContextChunk, ProviderType

logger = logging.getLogger(__name__)

class ToolProvider:
    """Gathers context about available tools."""
    
    def __init__(self, registry: Registry):
        self._registry = registry
        
    def gather(self, user_input: str) -> List[ContextChunk]:
        """Fetch available tools."""
        try:
            tool_names = self._registry.list_tools()
            if not tool_names:
                return []
                
            info = []
            for name in tool_names:
                tool = self._registry.get(name)
                if not tool:
                    continue
                actions = ", ".join(tool.get_actions())
                info.append(f"{name} (Actions: {actions})")
                
            content = "Available Tools: " + "; ".join(info)
            
            return [ContextChunk(
                content=content,
                provider=ProviderType.TOOL,
                relevance_score=0.5,
                recency_score=1.0,
                importance_score=0.6
            )]
        except Exception as e:
            logger.warning(f"Failed to gather tool context: {e}")
            return []
