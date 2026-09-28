"""
Prompt Enricher to inject consistency details into prompts.
"""

from typing import List

from .models import CharacterProfile, EnvironmentProfile, ObjectProfile


class PromptEnricher:
    """Enriches standard prompts with dense, consistent visual descriptors."""

    def enrich(
        self,
        base_prompt: str,
        characters: List[CharacterProfile],
        environments: List[EnvironmentProfile],
        objects: List[ObjectProfile]
    ) -> str:
        """
        Takes the base prompt and appends heavily structured visual descriptors 
        derived from the matched profiles to guide the diffusion models.
        """
        if not characters and not environments and not objects:
            return base_prompt

        enriched_parts = [base_prompt]
        enriched_parts.append("\n\n--- CONSISTENCY REFERENCES ---")
        
        if characters:
            enriched_parts.append("Characters in scene:")
            for c in characters:
                desc = f"- {c.name}: {c.description}"
                if c.clothing: desc += f", wearing {c.clothing}"
                if c.face_reference: desc += f", facial features: {c.face_reference}"
                if c.color_palette: desc += f", color palette: {c.color_palette}"
                enriched_parts.append(desc)
                
        if environments:
            enriched_parts.append("Environment setting:")
            for e in environments:
                desc = f"- {e.name}: {e.description}"
                if e.architecture_style: desc += f", architecture: {e.architecture_style}"
                if e.lighting: desc += f", lighting: {e.lighting}"
                enriched_parts.append(desc)
                
        if objects:
            enriched_parts.append("Objects/Props:")
            for o in objects:
                desc = f"- {o.name}: {o.description}"
                if o.material: desc += f", material: {o.material}"
                enriched_parts.append(desc)
                
        return "\n".join(enriched_parts)
