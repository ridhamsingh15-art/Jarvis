"""
Asset Matcher for NLP-based profile detection in prompts.
"""

import re
from typing import List, Tuple

from applications.content_factory.storyboard_engine.models import StoryboardScene
from .models import CharacterProfile, EnvironmentProfile, ObjectProfile
from .registry import ConsistencyRegistry


class AssetMatcher:
    """Detects references to registered profiles in text prompts."""

    def __init__(self, registry: ConsistencyRegistry) -> None:
        self._registry = registry

    def match_scene(
        self,
        project_id: str,
        scene: StoryboardScene
    ) -> Tuple[List[CharacterProfile], List[EnvironmentProfile], List[ObjectProfile]]:
        """
        Analyzes the scene's prompt to find mentioned characters, environments, and objects.
        """
        text = scene.image_prompt.lower()
        
        matched_chars = []
        for char in self._registry.list_characters(project_id):
            if self._word_in_text(char.name.lower(), text):
                matched_chars.append(char)
                
        matched_envs = []
        for env in self._registry.list_environments(project_id):
            if self._word_in_text(env.name.lower(), text):
                matched_envs.append(env)
                
        matched_objs = []
        for obj in self._registry.list_objects(project_id):
            if self._word_in_text(obj.name.lower(), text):
                matched_objs.append(obj)
                
        return matched_chars, matched_envs, matched_objs

    def _word_in_text(self, word: str, text: str) -> bool:
        """
        Simple bounded word match to avoid partial matches
        (e.g., 'ram' matching 'program').
        """
        pattern = r'\b' + re.escape(word) + r'\b'
        return bool(re.search(pattern, text))
