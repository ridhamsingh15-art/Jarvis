
class StructuredParser:
    """Cleans and strips raw HTML payloads into readable text blocks."""
    def parse(self, html: str) -> str:
        return html.replace("<html><body>", "").replace("</body></html>", "").strip()
