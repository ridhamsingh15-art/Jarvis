"""
Generator adapter for SEO Engine.
"""
import json

class SEOGenerator:
    """Mock generator for creating YouTube SEO metadata."""
    
    def generate(self, title: str, description: str) -> str:
        # Returns a JSON string containing mocked SEO payload
        data = {
            "youtube_title": f"{title} | Animated Short",
            "short_description": "Check out this animated story!",
            "long_description": description,
            "tags": ["animation", "story", "ai", "content"],
            "hashtags": ["#animation", "#story"],
            "chapters": [{"time": "00:00", "title": "Intro"}],
            "pinned_comment": "Subscribe for more videos!"
        }
        return json.dumps(data, indent=4)
