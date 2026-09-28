import logging
from typing import List
from core.cognition.context_models import ContextChunk, ContextPackage, ProviderType

logger = logging.getLogger(__name__)

class ContextRanker:
    """Ranks and filters context chunks to prevent prompt flooding."""
    
    def rank_and_package(self, chunks: List[ContextChunk]) -> ContextPackage:
        """Sorts chunks by total_score and populates the ContextPackage."""
        if not chunks:
            return ContextPackage()
            
        # Deduplicate based on content
        unique_chunks = {}
        for c in chunks:
            content_lower = c.content.lower().strip()
            if content_lower not in unique_chunks:
                unique_chunks[content_lower] = c
            else:
                if c.total_score > unique_chunks[content_lower].total_score:
                    unique_chunks[content_lower] = c
                    
        # Sort by total_score descending
        sorted_chunks = sorted(unique_chunks.values(), key=lambda x: x.total_score, reverse=True)
        
        # Limit to top 30 chunks overall to avoid flooding
        top_chunks = sorted_chunks[:30]
        
        package = ContextPackage()
        
        for c in top_chunks:
            if c.provider == ProviderType.MEMORY:
                package.memory_facts.append(c.content)
            elif c.provider == ProviderType.PKI:
                package.pki_knowledge.append(c.content)
            elif c.provider == ProviderType.WORKSPACE:
                package.workspace_state.append(c.content)
            elif c.provider == ProviderType.MISSION:
                package.mission_status.append(c.content)
            elif c.provider == ProviderType.PROJECT:
                package.active_projects.append(c.content)
            elif c.provider == ProviderType.TOOL:
                package.tool_state.append(c.content)
            elif c.provider == ProviderType.CONVERSATION:
                package.recent_conversation.append(c.content)
                
        return package
