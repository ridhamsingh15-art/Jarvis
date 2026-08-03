from typing import Any

from core.events.bus import EventBus
from core.models import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport

from .cache import InternetCache
from .crawler import WebCrawler
from .extractor import MetadataExtractor
from .parser import StructuredParser
from .scraper import ContentScraper
from .search import SearchEngine
from .summarizer import SemanticSummarizer
from .verifier import SourceVerifier


class InternetManager(RuntimeComponent):
    """Public API for Internet operations."""
    
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
        
    @property
    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(
            id=self._id.value,
            name="Internet Manager",
            version="1.0.0"
        )
        
    @property
    def state(self) -> ComponentState:
        return ComponentState.RUNNING if self._is_running else ComponentState.STOPPED
        
    async def initialize(self) -> None:
        pass
        
    async def start(self) -> None:
        self._is_running = True
        
    async def stop(self) -> None:
        self._is_running = False
        
    async def health(self) -> HealthReport:
        return HealthReport(
            component_id=self._id.value,
            state=HealthState.HEALTHY if self._is_running else HealthState.UNKNOWN
        )
        
    async def search(self, query: str) -> list[str]:
        await self.event_bus.publish_async(Event(topic="internet.search.started", payload={"query": query}))
        results = self.search_engine.search(query)
        await self.event_bus.publish_async(Event(topic="internet.search.completed", payload={"results": len(results)}))
        return results
        
    async def crawl(self, url: str, max_depth: int = 1) -> list[str]:
        links = self.crawler.crawl(url, max_depth)
        await self.event_bus.publish_async(Event(topic="internet.page.crawled", payload={"url": url, "links_found": len(links)}))
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
        await self.event_bus.publish_async(Event(topic="internet.summary.created", payload={"length": len(summary)}))
        return summary
        
    async def verify(self, content: str) -> bool:
        verified = self.verifier.verify(content)
        if verified:
            await self.event_bus.publish_async(Event(topic="internet.sources.verified", payload={"status": "verified"}))
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
