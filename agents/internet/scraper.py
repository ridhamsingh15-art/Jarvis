
class ContentScraper:
    """Simulates HTTP GET routines."""
    def scrape(self, url: str) -> str:
        return f"<html><body>Raw content for {url}</body></html>"
