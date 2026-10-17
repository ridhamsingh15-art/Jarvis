
import pytest

from agents.internet import InternetManager
from core.events.bus import EventBus


class MockLogger:
    def __init__(self):
        pass
    def info(self, *args, **kwargs):
        pass
    def error(self, *args, **kwargs):
        pass
    def debug(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass
    async def log_async(self, *args, **kwargs):
        pass


@pytest.fixture
def event_bus():
    return EventBus(MockLogger())

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
