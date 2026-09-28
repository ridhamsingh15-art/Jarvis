import logging
from typing import List
from applications.content_factory.project.manager import ProjectManager
from core.cognition.context_models import ContextChunk, ProviderType

logger = logging.getLogger(__name__)

class ProjectProvider:
    """Gathers context about active Content Factory projects."""
    
    def __init__(self, project_manager: ProjectManager):
        self._project_manager = project_manager
        
    def gather(self, user_input: str) -> List[ContextChunk]:
        """Fetch active projects and latest assets."""
        try:
            projects = self._project_manager.search_projects()
            if not projects:
                return []
                
            # Sort by updated_at descending and get the top 3
            recent_projects = sorted(projects, key=lambda p: p.updated_at, reverse=True)[:3]
            
            chunks = []
            for meta in recent_projects:
                try:
                    bundle = self._project_manager.get_project(meta.project_id)
                    assets_summary = f"{len(bundle.assets)} assets"
                    
                    content = f"Project: {meta.title} (ID: {meta.project_id})\nStatus: {meta.status}\nLast Updated: {meta.updated_at}\nAssets: {assets_summary}"
                    
                    chunks.append(ContextChunk(
                        content=content,
                        provider=ProviderType.PROJECT,
                        relevance_score=0.8, # We will refine this in ranker
                        recency_score=0.9,
                        importance_score=0.8
                    ))
                except Exception as e:
                    logger.warning(f"Failed to load project {meta.project_id}: {e}")
                    
            return chunks
        except Exception as e:
            logger.warning(f"Failed to gather project context: {e}")
            return []
