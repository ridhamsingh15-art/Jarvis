import json
import logging
from core.llm import LLMClient
from core.cognition.context import ShortTermContext
from core.executive.models import ExecutionStrategy, GoalType, Complexity
from core.executive.exceptions import ReasoningFailedError

logger = logging.getLogger(__name__)

class ReasoningEngine:
    """Analyzes user input to formulate an upfront ExecutionStrategy."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
        
    def analyze(self, user_input: str, context: ShortTermContext) -> ExecutionStrategy:
        """Determines the goal, complexity, and sub-system requirements."""
        
        history = "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in context.get_context_summary()["messages"][-3:]
        )
        
        prompt = f"""
You are the Executive Brain of JARVIS. Analyze the user's input and determine how the system should handle it.

User Input: "{user_input}"
Recent History: "{history}"

Evaluate the request based on these criteria:
1. Goal: "question", "conversation", "task", "research", "coding", "automation", "creative", "long_running_project"
2. Complexity: "simple", "medium", "complex", "very_complex"
3. Clarification: If the user's request is dangerously ambiguous, missing critical files/paths needed to begin, or completely non-sensical, set `requires_clarification` to true and provide the `clarification_question`. Otherwise, false and null.
4. Requires Memory: Does it rely on personal facts or preferences not present in recent history?
5. Requires Knowledge: Does it require searching the user's local indexed files (PKI) or reports?
6. Requires Tools: Does it require executing tasks (file edit, browser, shell, project creation)?
7. Requires Mission: Does it require a long-running background task (e.g. video generation, large builds)?
8. Requires Planning: Does it need a multi-step sequence?

Respond ONLY with valid JSON matching this schema:
{{
    "goal": "string",
    "complexity": "string",
    "requires_clarification": boolean,
    "clarification_question": "string or null",
    "requires_memory": boolean,
    "requires_knowledge": boolean,
    "requires_tools": boolean,
    "requires_mission": boolean,
    "requires_planning": boolean
}}
"""
        try:
            response = self._llm.generate("You are a helpful JSON-only assistant.", prompt)
            text = response.text if hasattr(response, "text") else str(response)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            data = json.loads(text.strip())
            
            try:
                goal = GoalType(data.get("goal", "conversation").lower())
            except ValueError:
                goal = GoalType.CONVERSATION
                
            try:
                complexity = Complexity(data.get("complexity", "simple").lower())
            except ValueError:
                complexity = Complexity.SIMPLE
                
            return ExecutionStrategy(
                goal=goal,
                complexity=complexity,
                requires_clarification=bool(data.get("requires_clarification", False)),
                clarification_question=data.get("clarification_question"),
                requires_memory=bool(data.get("requires_memory", False)),
                requires_knowledge=bool(data.get("requires_knowledge", False)),
                requires_tools=bool(data.get("requires_tools", False)),
                requires_mission=bool(data.get("requires_mission", False)),
                requires_planning=bool(data.get("requires_planning", False))
            )
        except Exception as e:
            logger.warning(f"Executive reasoning failed: {e}. Falling back to default strategy.")
            # Fallback safe strategy
            return ExecutionStrategy(
                goal=GoalType.CONVERSATION,
                complexity=Complexity.SIMPLE,
                requires_memory=True,
                requires_tools=True
            )
