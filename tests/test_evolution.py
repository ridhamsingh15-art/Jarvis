"""
Tests for the Self-Evolution Framework.
"""
import pytest
from unittest.mock import Mock

from core.evolution.models import ProposalState, Priority, RiskLevel, EvolutionProposal
from core.evolution.proposal import ProposalManager
from core.evolution.manager import EvolutionManager
from core.evolution.exceptions import ApprovalRequiredError

class TestProposalManager:
    def test_deduplication(self):
        manager = ProposalManager()
        p1 = EvolutionProposal(
            problem="High latency in API.",
            evidence="Logs", impact="Slow UI", recommended_solution="Cache",
            affected_modules=["api"], estimated_complexity="Low",
            estimated_risk=RiskLevel.LOW, priority=Priority.LOW
        )
        p2 = EvolutionProposal(
            problem="High latency in API.",
            evidence="Other logs", impact="Slow UI", recommended_solution="Cache",
            affected_modules=["api"], estimated_complexity="Low",
            estimated_risk=RiskLevel.LOW, priority=Priority.LOW
        )
        
        saved_p1 = manager.add_proposal(p1)
        assert saved_p1.state == ProposalState.DRAFT
        
        saved_p2 = manager.add_proposal(p2)
        # Should be rejected as duplicate
        assert saved_p2.state == ProposalState.REJECTED
        assert saved_p2.duplicate_of == saved_p1.id

class TestEvolutionManager:
    def test_analysis_and_roadmap(self):
        # Mocks
        llm = Mock()
        world = Mock()
        mission = Mock()
        experience = Mock()
        se = Mock()
        
        manager = EvolutionManager(llm, world, mission, experience, se)
        
        # Analyze should generate proposals based on the stubbed metrics
        proposals = manager.analyze_system()
        assert len(proposals) > 0
        
        # Check roadmap
        roadmap = manager.get_roadmap()
        assert len(roadmap.proposals) > 0
        
    def test_approval_workflow(self):
        llm = Mock()
        world = Mock()
        mission = Mock()
        experience = Mock()
        se = Mock()
        
        manager = EvolutionManager(llm, world, mission, experience, se)
        proposals = manager.analyze_system()
        p_id = proposals[0].id
        
        # Try to implement without approval (should fail)
        with pytest.raises(ApprovalRequiredError):
            manager.implement_proposal(p_id)
            
        # Approve
        manager.approve_proposal(p_id)
        
        # Implement should now succeed
        manager.implement_proposal(p_id)
        
        # Verify state
        p = manager.proposals.get_proposal(p_id)
        assert p.state == ProposalState.IMPLEMENTED
