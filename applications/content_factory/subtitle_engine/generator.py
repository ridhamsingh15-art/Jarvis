"""
Generator adapter for Subtitle Engine.
"""
from typing import List
from .models import SubtitleGenerationRequest

class SubtitleGenerator:
    """Generates SRT/VTT formatted text from requests."""
    
    def generate_srt(self, requests: List[SubtitleGenerationRequest]) -> str:
        lines = []
        for i, req in enumerate(requests):
            lines.append(str(i + 1))
            start = self._format_srt_time(req.start_time)
            end = self._format_srt_time(req.end_time)
            lines.append(f"{start} --> {end}")
            lines.append(f"[{req.speaker}] {req.text}" if req.speaker else req.text)
            lines.append("")
        return "\n".join(lines)
        
    def _format_srt_time(self, seconds: float) -> str:
        ms = int((seconds % 1) * 1000)
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
