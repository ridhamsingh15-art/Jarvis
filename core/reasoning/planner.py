import json
import logging
from typing import List, Optional
from core.llm import LLMClient
from core.cognition.context import ShortTermContext
from core.reasoning.execution_plan import ExecutionPlan

logger = logging.getLogger(__name__)

class ReasoningPlanner:
    """Drafts an ExecutionPlan based on user input, context, and iterative feedback."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        
    def plan(
        self, 
        user_input: str, 
        context: ShortTermContext, 
        previous_plan: Optional[ExecutionPlan] = None,
        feedback: Optional[str] = None,
        verification_errors: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """Generates a drafted ExecutionPlan."""
        
        history = "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in context.get_context_summary()["messages"][-3:]
        )
        
        system_prompt = "You are the Reasoning Planner of JARVIS. Draft an execution plan."
        
        prompt = f"""
User Input: "{user_input}"
Recent History: "{history}"

"""
        if previous_plan:
            prompt += f"Previous Drafted Plan:\n{json.dumps(previous_plan.__dict__, indent=2)}\n\n"
            
        if feedback:
            prompt += f"Critique Feedback to address:\n{feedback}\n\n"
            
        if verification_errors:
            prompt += f"Verification Errors to fix:\n{', '.join(verification_errors)}\n\n"
            
        prompt += """
Based on this, draft an ExecutionPlan.
Consider:
- ordered_steps: A list of discrete actions JARVIS should take.
- required_context: E.g. 'memory', 'knowledge', 'project', 'workspace'.
- required_tools: Names of tools needed (e.g. 'file', 'shell', 'browser').
- required_models: Any specific model requirements (e.g. 'reasoning', 'coding').
- required_missions: Names of any missions required.
- fallback_strategy: What to do if the primary plan fails.

Respond ONLY with valid JSON matching this schema:
{
    "ordered_steps": ["step 1", "step 2"],
    "required_context": ["memory"],
    "required_tools": ["tool_a"],
    "required_models": ["coding"],
    "required_missions": [],
    "fallback_strategy": "string"
}
"""
        
        try:
            resp = self._llm.generate(system_prompt, prompt)
            text = resp.text if hasattr(resp, "text") else str(resp)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            data = json.loads(text.strip())
            
            req_ctx = data.get("required_context", [])
            plan = ExecutionPlan(
                ordered_steps=data.get("ordered_steps", []),
                required_context=req_ctx,
                required_tools=data.get("required_tools", []),
                required_models=data.get("required_models", []),
                required_missions=data.get("required_missions", []),
                fallback_strategy=data.get("fallback_strategy", ""),
                requires_memory="memory" in req_ctx,
                requires_knowledge="knowledge" in req_ctx,
                requires_project="project" in req_ctx,
            )
            return plan
            
        except Exception as e:
            logger.warning(f"Reasoning planner failed: {e}. Falling back to default.")
            return ExecutionPlan(
                ordered_steps=[f"Address user request: {user_input}"],
                fallback_strategy="Ask user for clarification."
            )
