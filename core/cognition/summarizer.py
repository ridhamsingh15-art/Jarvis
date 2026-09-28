from typing import List
from core.cognition.models import RetrievedMemory, CognitiveContext, MemoryType

class MemorySummarizer:
    """Compresses retrieved memories into a structured CognitiveContext."""
    
    def summarize(self, memories: List[RetrievedMemory]) -> CognitiveContext:
        """Groups memories by type and compresses them into a CognitiveContext."""
        context = CognitiveContext()
        
        for m in memories:
            text = m.content.strip()
            # truncate excessively long texts
            if len(text) > 500:
                text = text[:497] + "..."
                
            if m.source == "pki":
                context.pki_results.append(text)
            elif m.memory_type == MemoryType.FACT or m.source == "sqlite_facts":
                context.user_facts.append(text)
            elif m.memory_type == MemoryType.CONTEXT or m.source == "sqlite_history":
                context.recent_context.append(text)
            else:
                context.recent_context.append(text)
                
        return context
