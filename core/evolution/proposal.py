"""
Proposal Manager.

Manages the lifecycle of a proposal (Draft -> Review -> Approved -> Implemented).
Ensures deduplication and merging of similar proposals.
"""
import logging
from typing import Optional
from .models import EvolutionProposal, ProposalState

logger = logging.getLogger(__name__)

class ProposalManager:
    """Manages evolution proposals and their state transitions."""

    def __init__(self):
        self._proposals: dict[str, EvolutionProposal] = {}

    def add_proposal(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """
        Add a new proposal. 
        If a similar proposal exists, it might be marked as a duplicate.
        """
        # Deduplication logic stub
        for existing in self._proposals.values():
            if existing.problem == proposal.problem and existing.state != ProposalState.IMPLEMENTED:
                logger.info(f"Proposal {proposal.id} is a duplicate of {existing.id}.")
                duplicate = EvolutionProposal(
                    id=proposal.id,
                    problem=proposal.problem,
                    evidence=proposal.evidence,
                    impact=proposal.impact,
                    recommended_solution=proposal.recommended_solution,
                    affected_modules=proposal.affected_modules,
                    estimated_complexity=proposal.estimated_complexity,
                    estimated_risk=proposal.estimated_risk,
                    priority=proposal.priority,
                    state=ProposalState.REJECTED,
                    duplicate_of=existing.id
                )
                self._proposals[duplicate.id] = duplicate
                return duplicate

        logger.info(f"Adding new proposal: {proposal.id}")
        self._proposals[proposal.id] = proposal
        return proposal

    def update_state(self, proposal_id: str, new_state: ProposalState) -> None:
        """Update the state of a proposal."""
        if proposal_id not in self._proposals:
            raise KeyError(f"Proposal {proposal_id} not found.")
            
        current = self._proposals[proposal_id]
        
        # State machine validations could go here
        
        updated = EvolutionProposal(
            id=current.id,
            problem=current.problem,
            evidence=current.evidence,
            impact=current.impact,
            recommended_solution=current.recommended_solution,
            affected_modules=current.affected_modules,
            estimated_complexity=current.estimated_complexity,
            estimated_risk=current.estimated_risk,
            priority=current.priority,
            state=new_state,
            duplicate_of=current.duplicate_of
        )
        self._proposals[proposal_id] = updated
        logger.debug(f"Proposal {proposal_id} transitioned to {new_state.value}")

    def get_proposal(self, proposal_id: str) -> Optional[EvolutionProposal]:
        return self._proposals.get(proposal_id)

    def get_all(self) -> list[EvolutionProposal]:
        return list(self._proposals.values())
