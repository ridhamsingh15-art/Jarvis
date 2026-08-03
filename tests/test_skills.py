from unittest.mock import MagicMock

import pytest

from core.events.bus import EventBus
from core.models.primitives import Identifier
from core.runtime.enums import ComponentState, HealthState
from core.skills import (
    DefaultSkillValidator,
    DuplicateSkillError,
    InMemorySkillRepository,
    LightweightSkillMatcher,
    Skill,
    SkillManager,
    SkillNotFoundError,
    SkillRegistry,
    SkillType,
    SkillValidationError,
)


@pytest.fixture
def repo():
    return InMemorySkillRepository()


@pytest.fixture
def validator(repo):
    # Dummy workflow checker that always returns True for testing
    return DefaultSkillValidator(repo, workflow_checker=lambda x: True)


@pytest.fixture
def matcher():
    return LightweightSkillMatcher()


@pytest.fixture
def registry(repo):
    return SkillRegistry(repo)


@pytest.fixture
def manager(registry, matcher, validator):
    logger = MagicMock()
    event_bus = EventBus(logger)
    return SkillManager(registry, matcher, validator, event_bus, logger)


def test_repository_crud(repo):
    skill = Skill(name="TestSkill", description="A test skill", skill_type=SkillType.USER)
    
    # Create
    repo.register(skill)
    assert repo.exists(skill.id)
    assert repo.get(skill.id) == skill
    
    # Duplicate
    with pytest.raises(DuplicateSkillError):
        repo.register(skill)
        
    # Update
    updated_skill = Skill(
        id=skill.id,
        name="UpdatedSkill",
        description="Updated desc",
        skill_type=SkillType.USER,
        version=skill.version,
        status=skill.status,
        workflow_id=skill.workflow_id,
        required_tools=skill.required_tools,
        required_permissions=skill.required_permissions,
        tags=skill.tags,
        metadata=skill.metadata
    )
    repo.update(updated_skill)
    assert repo.get(skill.id).name == "UpdatedSkill"
    
    # Read / List
    assert len(repo.list()) == 1
    
    # Delete
    assert repo.remove(skill.id) is True
    assert not repo.exists(skill.id)
    
    # Update non-existent
    with pytest.raises(SkillNotFoundError):
        repo.update(skill)


def test_validator():
    validator = DefaultSkillValidator(repository=None, workflow_checker=lambda w: w.value == "valid")
    
    # Valid
    valid_skill = Skill(name="Valid", description="desc", skill_type=SkillType.USER)
    validator.validate(valid_skill)
    
    # Empty name
    with pytest.raises(SkillValidationError):
        validator.validate(Skill(name="", description="", skill_type=SkillType.USER))
        
    # Invalid workflow
    with pytest.raises(SkillValidationError):
        invalid_wf_skill = Skill(
            name="Test", 
            description="desc", 
            skill_type=SkillType.USER,
            workflow_id=Identifier("invalid")
        )
        validator.validate(invalid_wf_skill)
        
    # Duplicate tags
    with pytest.raises(SkillValidationError):
        dup_tags_skill = Skill(
            name="Test", 
            description="desc", 
            skill_type=SkillType.USER,
            tags=["tag1", "tag1"]
        )
        validator.validate(dup_tags_skill)


def test_matcher(matcher):
    s1 = Skill(name="DataAnalysis", description="Analyze some data", skill_type=SkillType.USER, tags=["data", "math"])
    s2 = Skill(name="DataPlotting", description="Plot data", skill_type=SkillType.USER, tags=["data", "ui"])
    skills = [s1, s2]
    
    # Exact match
    matches = matcher.match("DataAnalysis", skills)
    assert matches[0].skill.name == "DataAnalysis"
    assert matches[0].score >= 100.0
    
    # Partial match
    matches = matcher.match("data", skills)
    assert len(matches) == 2
    # s1 gets more points because "data" is in name and description and tags
    # Let's just ensure both match something
    assert all(m.score > 0 for m in matches)
    
    # Tag match
    matches = matcher.match("ui", skills)
    assert len(matches) == 1
    assert matches[0].skill.name == "DataPlotting"


def test_registry(registry):
    skill = Skill(name="BuiltinSkill", description="Builtin", skill_type=SkillType.USER)
    
    # register_builtin forces BUILTIN type
    registry.register_builtin(skill)
    registered = registry.get(skill.id)
    assert registered.skill_type == SkillType.BUILTIN


@pytest.mark.asyncio
async def test_manager_lifecycle(manager):
    assert manager.state == ComponentState.INITIALIZED
    
    await manager.start()
    assert manager.state == ComponentState.RUNNING
    
    health = await manager.health()
    assert health.state == HealthState.HEALTHY
    
    await manager.stop()
    assert manager.state == ComponentState.STOPPED


def test_manager_operations(manager):
    skill = Skill(name="OpSkill", description="desc", skill_type=SkillType.USER)
    
    # Register
    manager.register_skill(skill)
    assert manager.get_skill(skill.id) is not None
    
    # Match
    matches = manager.match_skill("OpSkill")
    assert len(matches) == 1
    
    # Update
    updated = Skill(
        id=skill.id,
        name="UpdatedOpSkill",
        description="Updated desc",
        skill_type=SkillType.USER,
        version=skill.version,
        status=skill.status,
        workflow_id=skill.workflow_id,
        required_tools=skill.required_tools,
        required_permissions=skill.required_permissions,
        tags=skill.tags,
        metadata=skill.metadata
    )
    manager.update_skill(updated)
    assert manager.get_skill(skill.id).name == "UpdatedOpSkill"
    
    # Remove
    manager.remove_skill(skill.id)
    assert manager.get_skill(skill.id) is None
