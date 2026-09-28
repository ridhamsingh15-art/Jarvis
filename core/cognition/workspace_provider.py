import os
import logging
from pathlib import Path
from typing import List
from core.cognition.context_models import ContextChunk, ProviderType

logger = logging.getLogger(__name__)

class WorkspaceProvider:
    """Gathers context about the physical workspace."""
    
    def gather(self, user_input: str) -> List[ContextChunk]:
        """Fetch workspace path and layout."""
        try:
            cwd = Path.cwd()
            
            content = f"Working Directory: {cwd}\n"
            
            return [ContextChunk(
                content=content,
                provider=ProviderType.WORKSPACE,
                relevance_score=0.5,
                recency_score=1.0,
                importance_score=0.5
            )]
        except Exception as e:
            logger.warning(f"Failed to gather workspace context: {e}")
            return []
