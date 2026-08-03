from .interfaces import SkillMatcher
from .models import Skill, SkillMatch


class LightweightSkillMatcher(SkillMatcher):
    """
    Lightweight matcher that scores skills based on exact match,
    case-insensitive match, partial match, and tag matching.
    """

    def match(self, query: str, skills: list[Skill]) -> list[SkillMatch]:
        if not query or not query.strip():
            return []

        query_clean = query.strip()
        query_lower = query_clean.lower()
        query_tokens = set(query_lower.split())

        matches: list[SkillMatch] = []

        for skill in skills:
            score = 0.0
            reasons = []

            # 1. Exact match (highest priority)
            if skill.name == query_clean:
                score += 100.0
                reasons.append("Exact name match")
            
            # 2. Case-insensitive exact match
            elif skill.name.lower() == query_lower:
                score += 80.0
                reasons.append("Case-insensitive name match")

            # 3. Partial name match
            elif query_lower in skill.name.lower():
                score += 50.0
                reasons.append("Partial name match")
                
            # 4. Description partial match
            if skill.description and query_lower in skill.description.lower():
                score += 30.0
                reasons.append("Description match")

            # 5. Tag match
            if skill.tags:
                matched_tags = [tag for tag in skill.tags if tag.lower() in query_tokens]
                if matched_tags:
                    tag_score = len(matched_tags) * 10.0
                    score += tag_score
                    reasons.append(f"Matched {len(matched_tags)} tags")

            if score > 0:
                matches.append(SkillMatch(
                    skill=skill,
                    score=score,
                    reason=", ".join(reasons)
                ))

        # Sort matches by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches
