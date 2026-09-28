import logging
from typing import List
from core.mission.manager import MissionManager
from core.cognition.context_models import ContextChunk, ProviderType

logger = logging.getLogger(__name__)

class MissionProvider:
    """Gathers context about active, completed, and failed missions."""
    
    def __init__(self, mission_manager: MissionManager):
        self._mission_manager = mission_manager
        
    def gather(self, user_input: str) -> List[ContextChunk]:
        """Fetch mission statuses and progress."""
        try:
            missions = self._mission_manager.list()
            if not missions:
                return []
                
            # Filter to active or recently updated missions
            recent_missions = sorted(missions, key=lambda m: m.updated_at, reverse=True)[:5]
            
            chunks = []
            for m in recent_missions:
                content = f"Mission: {m.objective}\nStatus: {m.status.value}\nProgress: {m.progress}%\nLast Updated: {m.updated_at}"
                
                # Active missions have higher importance
                importance = 0.9 if m.status.value in ("running", "ready", "planning", "queued", "paused") else 0.5
                
                chunks.append(ContextChunk(
                    content=content,
                    provider=ProviderType.MISSION,
                    relevance_score=0.7,
                    recency_score=0.9,
                    importance_score=importance
                ))
                    
            return chunks
        except Exception as e:
            logger.warning(f"Failed to gather mission context: {e}")
            return []
