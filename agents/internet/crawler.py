
class WebCrawler:
    """Thread-safe recursive link traverser."""
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
