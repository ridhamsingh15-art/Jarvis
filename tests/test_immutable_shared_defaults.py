import pytest

from applications.content_factory.image_engine.adapters import ImageAdapterRegistry
from applications.content_factory.project.storage import ProjectStorage
from applications.content_factory.storyboard_engine.prompts import PromptAdapterRegistry
from core.mission_verifier import MissionCompletionVerifier


def test_image_adapter_registry_is_read_only_but_lookup_still_works():
    assert ImageAdapterRegistry.get("flux") is ImageAdapterRegistry._adapters["flux"]
    with pytest.raises(TypeError):
        ImageAdapterRegistry._adapters["new-adapter"] = object()


def test_prompt_adapter_registry_is_read_only_but_lookup_still_works():
    assert PromptAdapterRegistry.get("wan") is PromptAdapterRegistry._adapters["wan"]
    with pytest.raises(TypeError):
        PromptAdapterRegistry._adapters["new-adapter"] = object()


def test_required_project_directories_are_immutable():
    assert isinstance(ProjectStorage.REQUIRED_DIRS, tuple)
    assert "images" in ProjectStorage.REQUIRED_DIRS
    with pytest.raises(AttributeError):
        ProjectStorage.REQUIRED_DIRS.append("secrets")


def test_verifier_default_checks_cannot_be_mutated_between_instances():
    verifier = MissionCompletionVerifier()
    verifier._extra_checks.append(object())

    second = MissionCompletionVerifier()
    assert second._extra_checks == []
    assert isinstance(MissionCompletionVerifier._DEFAULT_CHECKS, tuple)
    with pytest.raises(AttributeError):
        MissionCompletionVerifier._DEFAULT_CHECKS.append(object())
