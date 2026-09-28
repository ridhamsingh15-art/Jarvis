import logging
from core.llm import LLMClient
from core.cognition.context import ShortTermContext
from core.knowledge.indexer.manager import KnowledgeManager
from memory.memory_manager import MemoryManager

from .retrieval import MemoryRetriever
from .ranking import MemoryRanker
from .summarizer import MemorySummarizer
from .injector import ContextInjector
from .models import RetrievedMemory

logger = logging.getLogger(__name__)

class MemoryOrchestrator:
    """The central gateway between ConversationEngine and Memory/PKI."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        memory_manager: MemoryManager,
        knowledge_manager: KnowledgeManager
    ):
        self._retriever = MemoryRetriever(llm_client, memory_manager, knowledge_manager)
        self._ranker = MemoryRanker()
        self._summarizer = MemorySummarizer()
        self._injector = ContextInjector()
        
    def prepare_context(self, user_input: str, short_term_context: ShortTermContext) -> str:
        """
        Automatically retrieves, ranks, summarizes, and formats memories 
        for injection into the LLM system prompt.
        """
        try:
            # 1. Retrieve
            raw_memories = self._retriever.retrieve(user_input)
            
            # 2. Rank
            ranked_memories = self._ranker.rank(raw_memories, user_input, max_items=15)
            
            # 3. Summarize/Group
            cognitive_context = self._summarizer.summarize(ranked_memories)
            
            # 4. Inject
            injected_string = self._injector.inject(cognitive_context)
            
            return injected_string
        except Exception as e:
            logger.exception(f"Memory orchestration failed: {e}")
            return ""
