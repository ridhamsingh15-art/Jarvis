import logging
from typing import Optional
from core.llm import LLMClient
from core.cognition.context import ShortTermContext
from core.registry import Registry
from core.reasoning.models import ReasoningState
from core.reasoning.execution_plan import ExecutionPlan
from core.reasoning.exceptions import MaxIterationsExceededError
from core.reasoning.planner import ReasoningPlanner
from core.reasoning.critic import ReasoningCritic
from core.reasoning.verifier import ReasoningVerifier

logger = logging.getLogger(__name__)

class ReasoningLoop:
    """The iterative deliberation state machine."""
    
    def __init__(self, llm_client: LLMClient, registry: Registry):
        self._planner = ReasoningPlanner(llm_client)
        self._critic = ReasoningCritic(llm_client)
        self._verifier = ReasoningVerifier(registry)
        
    def run(self, user_input: str, context: ShortTermContext, max_iterations: int = 3) -> ExecutionPlan:
        """Executes the loop: Think -> Evaluate -> Verify -> Revise -> Finalize"""
        
        logger.info(f"Starting Reasoning Loop for input: '{user_input}'")
        
        state = ReasoningState.THINK
        plan: Optional[ExecutionPlan] = None
        feedback: Optional[str] = None
        verification_errors = []
        
        iteration = 0
        
        while True:
            logger.info(f"Reasoning Loop Iteration {iteration} - State: {state.value}")
            
            if state == ReasoningState.THINK or state == ReasoningState.REVISE:
                iteration += 1
                if iteration > max_iterations:
                    logger.warning(f"Reasoning Loop exceeded max iterations ({max_iterations}). Forcing completion.")
                    return plan or ExecutionPlan(ordered_steps=["Error: Could not formulate a valid plan."])
                    
                plan = self._planner.plan(user_input, context, plan, feedback, verification_errors)
                state = ReasoningState.EVALUATE
                
            if state == ReasoningState.EVALUATE:
                critique = self._critic.critique(user_input, plan)
                
                if critique.needs_clarification:
                    logger.info("Reasoning Loop determined clarification is required.")
                    plan.requires_clarification = True
                    plan.clarification_question = critique.clarification_question
                    state = ReasoningState.FINALIZE
                elif not critique.is_complete:
                    logger.info("Reasoning Loop critic requested revisions.")
                    feedback = critique.feedback
                    state = ReasoningState.REVISE
                else:
                    state = ReasoningState.VERIFY
                    
            if state == ReasoningState.VERIFY:
                verification = self._verifier.verify(plan)
                if not verification.is_valid:
                    logger.info(f"Reasoning Loop verification failed: {verification.errors}")
                    verification_errors = verification.errors
                    feedback = "Verification failed. Fix errors."
                    state = ReasoningState.REVISE
                else:
                    state = ReasoningState.FINALIZE
                    
            if state == ReasoningState.FINALIZE:
                logger.info("Reasoning Loop complete. Finalizing plan.")
                return plan

