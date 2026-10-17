import builtins
from collections import defaultdict

from .enums import ConsensusStrategy, VoteType
from .interfaces import IVotingMechanism
from .models import Vote


class VotingEngine(IVotingMechanism):
    """Evaluates consensus algorithms across agent votes."""

    def evaluate(self, votes: builtins.list[Vote], strategy: ConsensusStrategy) -> Vote | None:
        if not votes:
            return None

        if strategy == ConsensusStrategy.MAJORITY:
            return self._evaluate_majority(votes)
            
        if strategy == ConsensusStrategy.WEIGHTED:
            return self._evaluate_weighted(votes)
            
        if strategy == ConsensusStrategy.UNANIMOUS:
            return self._evaluate_unanimous(votes)
            
        # Coordinator override always picks the highest weighted or first APPROVE
        if strategy == ConsensusStrategy.COORDINATOR_OVERRIDE:
            approves = [v for v in votes if v.decision == VoteType.APPROVE]
            if approves:
                return max(approves, key=lambda v: v.weight)
            return None

        return None

    def _evaluate_majority(self, votes: builtins.list[Vote]) -> Vote | None:
        counts: dict[VoteType, int] = defaultdict(int)
        for vote in votes:
            counts[vote.decision] += 1
            
        winning_decision = max(counts.items(), key=lambda x: x[1])[0]
        
        # Return any vote representing the winning decision
        for vote in votes:
            if vote.decision == winning_decision:
                return vote
        return None

    def _evaluate_weighted(self, votes: builtins.list[Vote]) -> Vote | None:
        weights: dict[VoteType, float] = defaultdict(float)
        for vote in votes:
            weights[vote.decision] += vote.weight
            
        winning_decision = max(weights.items(), key=lambda x: x[1])[0]
        
        for vote in votes:
            if vote.decision == winning_decision:
                return vote
        return None

    def _evaluate_unanimous(self, votes: builtins.list[Vote]) -> Vote | None:
        first_decision = votes[0].decision
        for vote in votes:
            if vote.decision != first_decision:
                return None
        return votes[0]
