import builtins

from core.events.bus import EventBus
from core.models.domain import Event
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.runtime.interfaces import RuntimeComponent
from core.runtime.models import ComponentMetadata, HealthReport
from core.telemetry import AsyncLogger

from .interfaces import SkillMatcher, SkillValidator
from .models import Skill, SkillMatch
from .registry import SkillRegistry


class SkillManager(RuntimeComponent):
    """
    Manager for the Skill System, integrating registry, matcher, and validator
    into the JARVIS AIOS runtime.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        matcher: SkillMatcher,
        validator: SkillValidator,
        event_bus: EventBus,
        logger: AsyncLogger,
    ) -> None:
        self._registry = registry
        self._matcher = matcher
        self._validator = validator
        self._event_bus = event_bus
        self._logger = logger
        
        self._state = ComponentState.INITIALIZED
        self._metadata = ComponentMetadata(
            id="core.skills",
            name="Skill System",
            version="1.0.0",
            dependencies=["core.events", "core.telemetry"]
        )

    @property
    def metadata(self) -> ComponentMetadata:
        return self._metadata

    @property
    def state(self) -> ComponentState:
        return self._state

    async def start(self) -> None:
        if self._state in (ComponentState.STARTING, ComponentState.RUNNING):
            return
            
        self._state = ComponentState.STARTING
        self._logger.info("Starting Skill System...")
        
        # Initialization logic (if any background tasks were needed, they would go here)
        
        self._state = ComponentState.RUNNING
        self._logger.info("Skill System started successfully.")

    async def stop(self) -> None:
        if self._state != ComponentState.RUNNING:
            return
            
        self._state = ComponentState.STOPPING
        self._logger.info("Stopping Skill System...")
        
        # Cleanup logic (if any)
        
        self._state = ComponentState.STOPPED
        self._logger.info("Skill System stopped.")

    async def health(self) -> HealthReport:
        try:
            # Perform a simple check to ensure registry is responsive
            self._registry.list()
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.HEALTHY,
                details={"skills_count": len(self._registry.list())}
            )
        except Exception as e:  # noqa: BLE001
            return HealthReport(
                component_id=self.metadata.id,
                state=HealthState.UNHEALTHY,
                error=str(e)
            )

    def register_skill(self, skill: Skill) -> None:
        """Register and validate a new skill, then publish an event."""
        self._validator.validate(skill)
        self._registry.register(skill)
        
        event = Event(
            topic="skill.registered",
            payload={"skill_id": skill.id.value, "skill_name": skill.name},
            source=self.metadata.id
        )
        self._event_bus.publish(event)

    def update_skill(self, skill: Skill) -> None:
        """Update and validate an existing skill, then publish an event."""
        self._validator.validate(skill)
        # Assuming registry uses repository directly and doesn't have update on its own.
        # Wait, SkillRegistry doesn't expose update(). I'll update it directly via repo or 
        # add update() to Registry.
        self._registry.update(skill)
        
        event = Event(
            topic="skill.updated",
            payload={"skill_id": skill.id.value, "skill_name": skill.name},
            source=self.metadata.id
        )
        self._event_bus.publish(event)

    def remove_skill(self, skill_id: Identifier) -> bool:
        """Remove a skill and publish an event if successful."""
        removed = self._registry.remove(skill_id)
        if removed:
            event = Event(
                topic="skill.removed",
                payload={"skill_id": skill_id.value},
                source=self.metadata.id
            )
            self._event_bus.publish(event)
        return removed

    def get_skill(self, skill_id: Identifier) -> Skill | None:
        return self._registry.get(skill_id)

    def list_skills(self) -> builtins.list[Skill]:
        return self._registry.list()

    def search_skills(
        self,
        id: Identifier | None = None,
        name: str | None = None,
        tags: builtins.list[str] | None = None
    ) -> builtins.list[Skill]:
        return self._registry.search(id=id, name=name, tags=tags)

    def match_skill(self, query: str) -> builtins.list[SkillMatch]:
        """Match a query against registered skills and publish an event."""
        skills = self._registry.list()
        matches = self._matcher.match(query, skills)
        
        event = Event(
            topic="skill.matched",
            payload={"query": query, "matches_count": len(matches)},
            source=self.metadata.id
        )
        self._event_bus.publish(event)
        
        return matches
