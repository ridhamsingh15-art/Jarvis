from core.cognition.models import CognitiveContext

class ContextInjector:
    """Formats the cognitive context into text ready for prompt injection."""
    
    def inject(self, context: CognitiveContext) -> str:
        """Constructs the prompt string to inject."""
        sections = []
        
        if context.user_facts:
            facts_str = "\n".join(f"- {f}" for f in context.user_facts)
            sections.append(f"# Relevant User Facts\n{facts_str}")
            
        if context.recent_context:
            context_str = "\n".join(f"- {c}" for c in context.recent_context)
            sections.append(f"# Recent Context\n{context_str}")
            
        if context.pki_results:
            pki_str = "\n".join(f"- {p}" for p in context.pki_results)
            sections.append(f"# PKI Results\n{pki_str}")
            
        if context.active_projects:
            proj_str = "\n".join(f"- {p}" for p in context.active_projects)
            sections.append(f"# Active Projects\n{proj_str}")
            
        return "\n\n".join(sections)
