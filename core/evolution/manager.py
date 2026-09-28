"""
Evolution Manager.

Central facade for the Self-Evolution Framework.
"""
import logging
from typing import Any

from .models import EvolutionProposal, ProposalState, EvolutionRoadmap
from .metrics import MetricsCollector
from .profiler import SystemProfiler
from .analyzer import EvolutionAnalyzer
from .planner import EvolutionPlanner
from .proposal import ProposalManager
from .roadmap import RoadmapManager
from .validator import EvolutionValidator
from .exceptions import ApprovalRequiredError

logger = logging.getLogger(__name__)

class EvolutionManager:
    """Facade for continuous system evolution."""

    def __init__(self, llm_client: Any, world_model: Any, mission_control: Any, experience_engine: Any, software_engineer: Any):
        self._llm_client = llm_client
        self._software_engineer = software_engineer
        
        self.metrics = MetricsCollector(world_model, mission_control)
        self.profiler = SystemProfiler()
        self.analyzer = EvolutionAnalyzer(self.metrics, self.profiler, experience_engine)
        self.planner = EvolutionPlanner(llm_client)
        self.proposals = ProposalManager()
        self.roadmap = RoadmapManager()
        self.validator = EvolutionValidator()

    def analyze_system(self) -> list[EvolutionProposal]:
        """Run a full analysis and generate proposals."""
        logger.info("Running system analysis for self-evolution...")
        
        issues = self.analyzer.analyze()
        new_proposals = []
        
        for issue in issues:
            proposal_draft = self.planner.create_proposal(issue)
            final_proposal = self.proposals.add_proposal(proposal_draft)
            
            # If it wasn't rejected as a duplicate
            if final_proposal.state != ProposalState.REJECTED:
                new_proposals.append(final_proposal)
                
        # Update the roadmap with the new proposals
        self.roadmap.update_roadmap(self.proposals.get_all())
        
        return new_proposals

    def approve_proposal(self, proposal_id: str) -> EvolutionProposal:
        """Explicitly approve a proposal for implementation."""
        logger.info(f"User approved proposal {proposal_id}")
        self.proposals.update_state(proposal_id, ProposalState.APPROVED)
        
        # Regenerate roadmap
        self.roadmap.update_roadmap(self.proposals.get_all())
        return self.proposals.get_proposal(proposal_id)

    def implement_proposal(self, proposal_id: str) -> None:
        """
        Forward an approved proposal to the Software Engineering Framework.
        Raises ApprovalRequiredError if not approved.
        """
        proposal = self.proposals.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal {proposal_id} not found.")
            
        # 1. Validation (Safety Check)
        self.validator.assert_approved(proposal)
        
        # 2. Handoff to Software Engineer
        logger.info(f"Forwarding proposal {proposal.id} to Software Engineering Framework...")
        # Stub: self._software_engineer.implement(proposal)
        
        # 3. Mark as Implemented
        self.proposals.update_state(proposal_id, ProposalState.IMPLEMENTED)
        self.roadmap.update_roadmap(self.proposals.get_all())

    def get_roadmap(self) -> EvolutionRoadmap:
        """Retrieve the current evolution roadmap."""
        return self.roadmap.get_roadmap()
