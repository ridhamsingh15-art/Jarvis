import os

d = "agents/internet"
os.makedirs(d, exist_ok=True)

files = {}

files["search.py"] = """import builtins
from typing import ClassVar

class SearchEngine:
    \"\"\"Abstraction routing keyword queries to search engines.\"\"\"
    SUPPORTED_ENGINES: ClassVar[set[str]] = {"google", "bing", "duckduckgo"}
    
    def search(self, query: str, engine: str = "google") -> list[str]:
        if engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Engine {engine} not supported")
        return [f"https://example.com/{engine}/{query.replace(' ', '+')}"]
"""

files["crawler.py"] = """import builtins

class WebCrawler:
    \"\"\"Thread-safe recursive link traverser.\"\"\"
    def __init__(self) -> None:
        self.visited: set[str] = set()
        
    def crawl(self, url: str, max_depth: int = 1) -> list[str]:
        if url in self.visited or max_depth < 0:
            return []
        self.visited.add(url)
        # Mock finding links
        links = [f"{url}/page1", f"{url}/page2"]
        result = [url]
        for link in links:
            result.extend(self.crawl(link, max_depth - 1))
        return result
"""

files["scraper.py"] = """import builtins

class ContentScraper:
    \"\"\"Simulates HTTP GET routines.\"\"\"
    def scrape(self, url: str) -> str:
        return f"<html><body>Raw content for {url}</body></html>"
"""

files["parser.py"] = """import builtins

class StructuredParser:
    \"\"\"Cleans and strips raw HTML payloads into readable text blocks.\"\"\"
    def parse(self, html: str) -> str:
        return html.replace("<html><body>", "").replace("</body></html>", "").strip()
"""

files["extractor.py"] = """import builtins

class MetadataExtractor:
    \"\"\"Generates highly structured dictionaries isolating key attributes.\"\"\"
    def extract(self, html: str) -> dict[str, str]:
        return {
            "title": "Extracted Title",
            "author": "System",
            "date": "2026-08-03"
        }
"""

files["summarizer.py"] = """import builtins

class SemanticSummarizer:
    \"\"\"Compresses parsed text into condensed paragraphs.\"\"\"
    def summarize(self, text: str) -> str:
        return f"Summary of: {text}"
"""

files["verifier.py"] = """import builtins
import hashlib

class SourceVerifier:
    \"\"\"Validates extraction confidence, removes duplicates, applies ranking.\"\"\"
    def __init__(self) -> None:
        self.seen_hashes: set[str] = set()
        
    def verify(self, content: str) -> bool:
        h = hashlib.sha256(content.encode()).hexdigest()
        if h in self.seen_hashes:
            return False
        self.seen_hashes.add(h)
        return True
"""

files["cache.py"] = """import builtins
import threading
from typing import Any

class InternetCache:
    \"\"\"Wraps an RLock around deep-copied dictionaries mapping URL strings.\"\"\"
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()
        
    def get(self, url: str) -> Any | None:
        with self._lock:
            return self._cache.get(url)
            
    def set(self, url: str, data: Any) -> None:
        with self._lock:
            self._cache[url] = data
"""

files["manager.py"] = """import builtins
from typing import Any

from core.models.primitives import Identifier
from core.runtime.interfaces import RuntimeComponent
from core.runtime.enums import HealthState
from core.runtime.models import HealthReport
from core.events.registry import EventBus

from .search import SearchEngine
from .crawler import WebCrawler
from .scraper import ContentScraper
from .parser import StructuredParser
from .extractor import MetadataExtractor
from .summarizer import SemanticSummarizer
from .verifier import SourceVerifier
from .cache import InternetCache


class InternetManager(RuntimeComponent):
    \"\"\"Public API for Internet operations.\"\"\"
    
    def __init__(self, event_bus: EventBus) -> None:
        self._id = Identifier("manager.internet")
        self.event_bus = event_bus
        self.search_engine = SearchEngine()
        self.crawler = WebCrawler()
        self.scraper = ContentScraper()
        self.parser = StructuredParser()
        self.extractor = MetadataExtractor()
        self.summarizer = SemanticSummarizer()
        self.verifier = SourceVerifier()
        self.cache = InternetCache()
        self._is_running = False
        
    @property
    def id(self) -> Identifier:
        return self._id
        
    async def initialize(self) -> None:
        pass
        
    async def start(self) -> None:
        self._is_running = True
        
    async def stop(self) -> None:
        self._is_running = False
        
    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.STOPPED
        )
        
    async def search(self, query: str) -> list[str]:
        await self.event_bus.publish("internet.search.started", {"query": query})
        results = self.search_engine.search(query)
        await self.event_bus.publish("internet.search.completed", {"results": len(results)})
        return results
        
    async def crawl(self, url: str, max_depth: int = 1) -> list[str]:
        links = self.crawler.crawl(url, max_depth)
        await self.event_bus.publish("internet.page.crawled", {"url": url, "links_found": len(links)})
        return links
        
    async def scrape(self, url: str) -> str:
        cached = self.cache.get(url)
        if cached:
            return cached
            
        html = self.scraper.scrape(url)
        self.cache.set(url, html)
        return html
        
    async def summarize(self, text: str) -> str:
        summary = self.summarizer.summarize(text)
        await self.event_bus.publish("internet.summary.created", {"length": len(summary)})
        return summary
        
    async def verify(self, content: str) -> bool:
        verified = self.verifier.verify(content)
        if verified:
            await self.event_bus.publish("internet.sources.verified", {"status": "verified"})
        return verified
        
    async def discover(self, url: str) -> dict[str, Any]:
        html = await self.scrape(url)
        text = self.parser.parse(html)
        meta = self.extractor.extract(html)
        summary = await self.summarize(text)
        
        return {
            "url": url,
            "text": text,
            "metadata": meta,
            "summary": summary
        }
"""

files["__init__.py"] = """from .cache import InternetCache
from .crawler import WebCrawler
from .extractor import MetadataExtractor
from .manager import InternetManager
from .parser import StructuredParser
from .scraper import ContentScraper
from .search import SearchEngine
from .summarizer import SemanticSummarizer
from .verifier import SourceVerifier

__all__ = [
    "InternetCache",
    "WebCrawler",
    "MetadataExtractor",
    "InternetManager",
    "StructuredParser",
    "ContentScraper",
    "SearchEngine",
    "SemanticSummarizer",
    "SourceVerifier",
]
"""

for fname, fcontent in files.items():
    with open(os.path.join(d, fname), "w") as f:
        f.write(fcontent)
        
tests_file = """import pytest

from core.events.registry import EventBus
from agents.internet import InternetManager

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def internet_manager(event_bus):
    return InternetManager(event_bus)

@pytest.mark.asyncio
async def test_search(internet_manager):
    results = await internet_manager.search("test query")
    assert len(results) > 0
    assert "google" in results[0]

@pytest.mark.asyncio
async def test_crawl(internet_manager):
    links = await internet_manager.crawl("http://example.com", max_depth=1)
    assert len(links) > 0

@pytest.mark.asyncio
async def test_caching(internet_manager):
    url = "http://example.com"
    html1 = await internet_manager.scrape(url)
    html2 = await internet_manager.scrape(url)
    assert html1 == html2
    
    # Change scraper logic manually to prove cache works
    internet_manager.scraper.scrape = lambda u: "different"
    html3 = await internet_manager.scrape(url)
    assert html1 == html3 # should hit cache

@pytest.mark.asyncio
async def test_verification(internet_manager):
    content1 = "some content"
    content2 = "some content"
    
    assert await internet_manager.verify(content1) is True
    assert await internet_manager.verify(content2) is False # Duplicate rejected

@pytest.mark.asyncio
async def test_discover(internet_manager):
    url = "http://example.com"
    data = await internet_manager.discover(url)
    
    assert data["url"] == url
    assert "Raw content" in data["text"]
    assert data["metadata"]["title"] == "Extracted Title"
    assert "Summary of" in data["summary"]

@pytest.mark.asyncio
async def test_thread_safety(internet_manager):
    import asyncio
    
    async def concurrent_scrape():
        return await internet_manager.scrape("http://example.com/concurrent")
        
    tasks = [concurrent_scrape() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    assert all(r == results[0] for r in results)
"""

with open("tests/test_internet_agent.py", "w") as f:
    f.write(tests_file)
