import logging
import re
from typing import List, Any
from core.cognition.context import ShortTermContext
from core.cognition.context_models import ContextPackage, ContextChunk, ProviderType
from core.context_budget import (
    ContextBudget,
    ContextBudgetManager,
    estimate_tokens,
)

from .context_builder import ContextBuilder
from .context_ranker import ContextRanker
from .workspace_provider import WorkspaceProvider
from .mission_provider import MissionProvider
from .project_provider import ProjectProvider
from .tool_provider import ToolProvider
from .retrieval import MemoryRetriever

logger = logging.getLogger(__name__)

class ContextOrchestrator:
    """The central gateway for building the complete runtime context for every LLM request."""
    
    def __init__(
        self,
        workspace_provider: WorkspaceProvider,
        mission_provider: MissionProvider,
        project_provider: ProjectProvider,
        tool_provider: ToolProvider,
        memory_retriever: MemoryRetriever,
        llm_client: Any = None,  # kept for backwards-compat, no longer used
    ):
        self._builder = ContextBuilder()
        self._ranker = ContextRanker()
        self._budget_manager = ContextBudgetManager()
        self._last_budget: ContextBudget | None = None
        self._workspace_provider = workspace_provider
        self._mission_provider = mission_provider
        self._project_provider = project_provider
        self._tool_provider = tool_provider
        self._memory_retriever = memory_retriever

    @property
    def last_context_budget(self) -> ContextBudget | None:
        """Return the ContextBudget report from the most recent build() call."""
        return self._last_budget
        
    def build(
        self,
        user_input: str,
        short_term_context: ShortTermContext,
        plan: "ExecutionPlan" = None,
        intent: str = "chat",
    ) -> ContextPackage:
        """
        Dynamically selects providers based on ExecutionPlan or intent, gathers
        context, ranks it, and returns a ContextPackage.

        Args:
            user_input: The user's current message.
            short_term_context: Recent conversation history.
            plan: Optional ExecutionPlan — if provided, plan flags override intent.
            intent: Routing intent string ("chat", "tool", "memory", "mission").
        """
        try:
            # 1. Determine required providers (fully deterministic)
            selected_providers = self._builder.determine_providers(
                plan, user_input=user_input, intent=intent
            )
            logger.info(f"ContextBuilder selected providers: {[p.value for p in selected_providers]}")
            
            raw_chunks: List[ContextChunk] = []
            
            # 2. Gather from Memory/PKI
            if ProviderType.MEMORY in selected_providers or ProviderType.PKI in selected_providers:
                memories = self._memory_retriever.retrieve(user_input)
                for m in memories:
                    ptype = ProviderType.PKI if m.source == "pki" else ProviderType.MEMORY
                    raw_chunks.append(ContextChunk(
                        content=m.content,
                        provider=ptype,
                        relevance_score=m.relevance_score,
                        recency_score=0.8,
                        importance_score=0.7
                    ))
                    
            # 3. Gather from Projects
            if ProviderType.PROJECT in selected_providers:
                raw_chunks.extend(self._project_provider.gather(user_input))
                
            # 4. Gather from Missions
            if ProviderType.MISSION in selected_providers:
                raw_chunks.extend(self._mission_provider.gather(user_input))
                
            # 5. Gather from Workspace
            if ProviderType.WORKSPACE in selected_providers:
                raw_chunks.extend(self._workspace_provider.gather(user_input))
                
            # 6. Gather from Tools
            if ProviderType.TOOL in selected_providers:
                raw_chunks.extend(self._tool_provider.gather(user_input))
                
            # 7. Gather Recent Conversation
            if ProviderType.CONVERSATION in selected_providers:
                raw_messages = short_term_context.get_context_summary()["messages"]
                # Clean feedback loop observe prompts so raw tool envelopes don't bloat conversation history
                cleaned_messages = []
                for m in raw_messages:
                    c = m.get("content", "")
                    if "<UNTRUSTED_TOOL_RESULT>" in c and "Original user request:" in c:
                        match = re.search(r"Original user request: '([^']+)'", c)
                        if match:
                            cleaned_messages.append({"role": m.get("role", "user"), "content": match.group(1)})
                    else:
                        cleaned_messages.append(m)

                # Prioritize newest turns first within token budget (500 tokens)
                total_h_tokens = 0
                max_h_tokens = 500
                selected_lines = []
                for msg in reversed(cleaned_messages):
                    line = f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    t = estimate_tokens(line)
                    if total_h_tokens + t <= max_h_tokens:
                        selected_lines.append(line)
                        total_h_tokens += t
                    else:
                        break
                selected_lines.reverse()
                history = "\n".join(selected_lines)
                if history:
                    raw_chunks.append(ContextChunk(
                        content=history,
                        provider=ProviderType.CONVERSATION,
                        relevance_score=1.0,
                        recency_score=1.0,
                        importance_score=1.0
                    ))

            # 8. Rank and Package
            package = self._ranker.rank_and_package(raw_chunks)

            # 9. Apply Deterministic Context Budgeting
            self._last_budget = self._budget_manager.budget_context_package(
                package,
                user_input=user_input,
            )

            return package
            
        except Exception as e:
            logger.exception(f"Context orchestration failed: {e}")
            return ContextPackage()

