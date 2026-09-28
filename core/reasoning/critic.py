import json
import logging
from typing import Optional
from core.llm import LLMClient
from core.reasoning.models import CritiqueResult
from core.reasoning.execution_plan import ExecutionPlan

logger = logging.getLogger(__name__)

class ReasoningCritic:
    """Performs self-critique on a drafted ExecutionPlan."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        
    def critique(self, user_input: str, plan: ExecutionPlan) -> CritiqueResult:
        """Critiques the plan for completeness and missing information."""
        
        system_prompt = "You are the Reasoning Critic of JARVIS. Critique the execution plan."
        
        prompt = f"""
User Input: "{user_input}"

Drafted Plan:
{json.dumps(plan.__dict__, indent=2)}

Critique this plan based on the following criteria:
1. Is it complete? Are all necessary steps included?
2. Did we miss anything?
3. Can this be simplified?
4. Is the user's request dangerously ambiguous or missing critical information to start?

Respond ONLY with valid JSON matching this schema:
{{
    "is_complete": true or false,
    "feedback": "string explaining what needs to change, or empty if complete",
    "needs_clarification": true or false,
    "clarification_question": "string or null"
}}
"""
        try:
            resp = self._llm.generate(system_prompt, prompt)
            text = resp.text if hasattr(resp, "text") else str(resp)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            data = json.loads(text.strip())
            
            return CritiqueResult(
                is_complete=bool(data.get("is_complete", True)),
                feedback=data.get("feedback", ""),
                needs_clarification=bool(data.get("needs_clarification", False)),
                clarification_question=data.get("clarification_question")
            )
            
        except Exception as e:
            logger.warning(f"Reasoning critic failed: {e}. Assuming plan is complete.")
            return CritiqueResult(is_complete=True, feedback="")
