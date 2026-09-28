from typing import ClassVar


class SearchEngine:
    """Abstraction routing keyword queries to search engines."""
    SUPPORTED_ENGINES: ClassVar[set[str]] = {"google", "bing", "duckduckgo"}
    
    def search(self, query: str, engine: str = "google") -> list[str]:
        if engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Engine {engine} not supported")
        return [f"https://example.com/{engine}/{query.replace(' ', '+')}"]
