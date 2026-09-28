"""
Evolution Roadmap.

Generates and maintains the evolving backlog/roadmap of proposals.
"""
import logging
import time
from .models import EvolutionRoadmap, EvolutionProposal, ProposalState, Priority

logger = logging.getLogger(__name__)

class RoadmapManager:
    """Maintains the backlog of approved or pending proposals."""

    def __init__(self):
        self._roadmap = EvolutionRoadmap()

    def update_roadmap(self, all_proposals: list[EvolutionProposal]) -> EvolutionRoadmap:
        """Regenerate the roadmap based on current proposals."""
        logger.info("Updating evolution roadmap...")
        
        # Filter out rejected or implemented proposals
        active_proposals = [
            p for p in all_proposals 
            if p.state in (ProposalState.DRAFT, ProposalState.REVIEW, ProposalState.APPROVED)
        ]
        
        # Sort by priority (assuming a specific order mapping in a real impl, here we just group)
        def priority_weight(p: EvolutionProposal) -> int:
            weight_map = {
                Priority.HIGH: 100,
                Priority.MEDIUM: 50,
                Priority.LOW: 10,
                Priority.TECHNICAL_DEBT: 75,
                Priority.FUTURE_FEATURE: 5
            }
            return weight_map.get(p.priority, 0)
            
        active_proposals.sort(key=priority_weight, reverse=True)
        
        self._roadmap = EvolutionRoadmap(
            proposals=active_proposals,
            last_updated=time.time()
        )
        return self._roadmap

    def get_roadmap(self) -> EvolutionRoadmap:
        return self._roadmap
