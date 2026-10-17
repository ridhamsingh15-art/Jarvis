from collections import defaultdict

from .enums import PatternType
from .interfaces import PatternDetector
from .models import Experience, LearningPattern


class DeterministicPatternDetector(PatternDetector):
    """
    Analyzes experiences to detect deterministic patterns without AI.
    """

    def detect(self, experiences: list[Experience]) -> list[LearningPattern]:
        if not experiences:
            return []

        patterns: list[LearningPattern] = []
        
        # We can find repeated sequences of tasks.
        # But for simplicity, we focus on repeated skills and workflows,
        # and successful task sequences.
        
        patterns.extend(self._detect_skill_patterns(experiences))
        patterns.extend(self._detect_workflow_patterns(experiences))
        patterns.extend(self._detect_task_sequence_patterns(experiences))

        return patterns

    def _detect_skill_patterns(self, experiences: list[Experience]) -> list[LearningPattern]:
        patterns = []
        skill_groups: dict[str, list[Experience]] = defaultdict(list)
        
        for e in experiences:
            if e.skill_id:
                skill_groups[e.skill_id.value].append(e)
                
        for exps in skill_groups.values():
            success_count = sum(1 for e in exps if e.success)
            total = len(exps)
            confidence = (success_count / total) if total > 0 else 0.0
            
            patterns.append(LearningPattern(
                pattern_type=PatternType.SKILL,
                occurrences=total,
                confidence=confidence,
                source_experiences=[e.id for e in exps]
            ))
            
        return patterns

    def _detect_workflow_patterns(self, experiences: list[Experience]) -> list[LearningPattern]:
        patterns = []
        workflow_groups: dict[str, list[Experience]] = defaultdict(list)
        
        for e in experiences:
            if e.workflow_id:
                workflow_groups[e.workflow_id.value].append(e)
                
        for exps in workflow_groups.values():
            success_count = sum(1 for e in exps if e.success)
            total = len(exps)
            confidence = (success_count / total) if total > 0 else 0.0
            
            patterns.append(LearningPattern(
                pattern_type=PatternType.WORKFLOW,
                occurrences=total,
                confidence=confidence,
                source_experiences=[e.id for e in exps]
            ))
            
        return patterns

    def _detect_task_sequence_patterns(self, experiences: list[Experience]) -> list[LearningPattern]:
        patterns = []
        seq_groups: dict[tuple[str, ...], list[Experience]] = defaultdict(list)
        
        for e in experiences:
            if e.tasks:
                seq = tuple(e.tasks)
                seq_groups[seq].append(e)
                
        for exps in seq_groups.values():
            # A pattern is more meaningful if it repeats.
            if len(exps) > 1:
                success_count = sum(1 for e in exps if e.success)
                total = len(exps)
                confidence = (success_count / total) if total > 0 else 0.0
                
                patterns.append(LearningPattern(
                    pattern_type=PatternType.TASK_SEQUENCE,
                    occurrences=total,
                    confidence=confidence,
                    source_experiences=[e.id for e in exps]
                ))
                
        return patterns
