import json
import logging
from typing import List

from core.llm import LLMClient
from core.cognition.models import RetrievedMemory, MemoryType
from core.knowledge.indexer.manager import KnowledgeManager
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class MemoryRetriever:
    """Retrieves relevant facts and knowledge from memory and PKI."""
    
    def __init__(
        self, 
        llm_client: LLMClient, 
        memory_manager: MemoryManager,
        knowledge_manager: KnowledgeManager
    ):
        self._llm = llm_client
        self._memory_manager = memory_manager
        self._knowledge_manager = knowledge_manager

    def retrieve(self, user_input: str) -> List[RetrievedMemory]:
        """Determine if retrieval is needed and fetch memories/knowledge."""
        results = []
        
        # Always fetch explicitly stored user facts (preferences, identity) deterministically
        if hasattr(self._memory_manager, "_memory") and hasattr(self._memory_manager._memory, "get_all_facts"):
            try:
                all_facts = self._memory_manager._memory.get_all_facts()
                for k, v in all_facts.items():
                    results.append(RetrievedMemory(
                        content=f"Fact - {k}: {v}",
                        source="sqlite_facts",
                        relevance_score=1.0,
                        memory_type=MemoryType.FACT
                    ))
            except Exception as e:
                logger.debug("Failed to fetch facts: %s", e)
        
        queries = self._generate_search_queries(user_input)
        if not queries:
            return results
        
        for query in queries:
            # Search memory (SQLite conversation history)
            try:
                if hasattr(self._memory_manager, "_memory") and hasattr(self._memory_manager._memory, "search"):
                    memory_entries = self._memory_manager._memory.search(query, limit=5)
                    for entry in memory_entries:
                        results.append(RetrievedMemory(
                            content=f"Recent interaction: {entry.user_input} -> {entry.summary}",
                            source="sqlite_history",
                            relevance_score=0.8,
                            memory_type=MemoryType.CONTEXT
                        ))
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")
            
            # Search PKI
            try:
                if hasattr(self._knowledge_manager, "search"):
                    pki_entries = self._knowledge_manager.search(query, limit=5)
                    for pki in pki_entries:
                        doc_path = getattr(getattr(pki, "document", None), "path", getattr(pki, "filepath", "unknown"))
                        chunk_text = getattr(getattr(pki, "chunk", None), "text", getattr(pki, "text", ""))
                        score = getattr(pki, "score", 0.0)
                        results.append(RetrievedMemory(
                            content=f"Document ({doc_path}): {chunk_text}",
                            source="pki",
                            relevance_score=score,
                            memory_type=MemoryType.FACT
                        ))
            except Exception as e:
                logger.warning(f"PKI search failed: {e}")
                
        return results

    def _generate_search_queries(self, user_input: str) -> List[str]:
        """Uses fast heuristics or LLM to decide if memory/PKI search is needed."""
        cleaned = user_input.lower().strip()
        # Fast filter: Simple greetings or generic chatter don't need semantic memory retrieval
        greetings = ("hi", "hello", "hey", "who are you", "what can you do", "thanks", "thank you")
        if cleaned in greetings or any(cleaned.startswith(g) for g in ["hi ", "hello ", "hey "]):
            return []
            
        memory_keywords = ("remember", "recall", "what did i", "what is my", "where is", "yesterday", "find my", "search my", "file", "document", "project")
        if not any(k in cleaned for k in memory_keywords):
            # For general conversation, avoid an extra LLM call
            return []

        prompt = f"""
You are deciding whether to search JARVIS's memory for the user's input.
If the user is asking about past conversations, personal facts, their name, their projects, or asking you to continue work, you must search memory.
If it is a generic question (e.g. "What is 2+2?"), do not search.

User Input: "{user_input}"

Return a JSON array of search queries. Return an empty array if no search is needed.
Example: ["user name", "favourite IDE"]
"""
        try:
            response = self._llm.generate("You are a helpful JSON-only assistant.", prompt)
            text = response.text if hasattr(response, "text") else str(response)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            queries = json.loads(text.strip())
            if isinstance(queries, list):
                return queries
            return []
        except Exception as e:
            logger.warning(f"Failed to generate search queries: {e}")
            return [user_input]

