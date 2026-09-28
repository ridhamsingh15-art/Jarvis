"""
Safety Validator for the Self-Evolution Framework.

Ensures that no code execution or framework mutation can occur without explicit user approval.
"""
import logging
from .models import EvolutionProposal, ProposalState
from .exceptions import ApprovalRequiredError

logger = logging.getLogger(__name__)

class EvolutionValidator:
    """Enforces safety rules before delegating to Software Engineer."""

    def assert_approved(self, proposal: EvolutionProposal) -> None:
        """
        Verify that a proposal has been explicitly approved.
        Raises ApprovalRequiredError if it is not in the APPROVED state.
        """
        logger.info(f"Validating approval status for proposal {proposal.id}...")
        
        if proposal.state != ProposalState.APPROVED:
            logger.error(f"Validation failed for {proposal.id}. Current state: {proposal.state.value}")
            raise ApprovalRequiredError(
                f"Cannot implement proposal {proposal.id}. It requires explicit user approval. "
                f"Current state is {proposal.state.value}."
            )
            
        logger.info(f"Proposal {proposal.id} is approved for implementation.")
