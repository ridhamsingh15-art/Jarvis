from typing import List
from core.cognition.models import RetrievedMemory

class MemoryRanker:
    """Ranks retrieved memories and removes irrelevant/duplicate information."""
    
    def rank(self, memories: List[RetrievedMemory], user_input: str, max_items: int = 15) -> List[RetrievedMemory]:
        """
        Sorts memories by relevance score and filters out duplicates.
        In a full implementation, this could use an LLM cross-encoder to score
        the relevance of each fact against the user_input.
        """
        if not memories:
            return []
            
        # Deduplicate based on content
        unique_memories = {}
        for m in memories:
            # Simple content hash for deduplication
            content_lower = m.content.lower().strip()
            if content_lower not in unique_memories:
                unique_memories[content_lower] = m
            else:
                # Keep the one with the higher relevance score
                if m.relevance_score > unique_memories[content_lower].relevance_score:
                    unique_memories[content_lower] = m
                    
        # Sort by relevance score descending
        sorted_memories = sorted(unique_memories.values(), key=lambda x: x.relevance_score, reverse=True)
        
        return sorted_memories[:max_items]
