import pytest

from applications.software_engineer.architecture_designer import ArchitectureDesigner
from applications.software_engineer.code_generator import CodeGenerator
from applications.software_engineer.code_reviewer import CodeReviewer
from applications.software_engineer.dependency_manager import DependencyManager
from applications.software_engineer.documentation_engine import DocumentationEngine
from applications.software_engineer.models import (
    ArchitectureDesign,
    CodeDiff,
    ComponentDesign,
    DependencyGraph,
    ImplementationResult,
    RepositoryAnalysis,
)
from applications.software_engineer.refactoring_engine import RefactoringEngine
from applications.software_engineer.release_manager import ReleaseManager
from applications.software_engineer.security_reviewer import SecurityReviewer


def _analysis():
    return RepositoryAnalysis(
        dependency_graph=DependencyGraph(modules=[], imports={}),
        primary_language="Python",
        detected_frameworks=[],
        entry_points=[],
        relevant_files=[],
    )


def _design():
    return ArchitectureDesign(
        components=[
            ComponentDesign(
                component_name="Example",
                purpose="Example component",
                dependencies=[],
                files_to_modify=[],
                files_to_create=["example.py"],
            )
        ],
        architectural_patterns=[],
    )


def _implementation():
    return ImplementationResult(
        diffs=[CodeDiff(file_path="example.py", change_type="create", content="value = 1\n")],
        files_touched=["example.py"],
        compile_success=True,
    )


def test_architecture_designer_does_not_return_a_fake_stub_design():
    with pytest.raises(NotImplementedError, match="no synthetic design"):
        ArchitectureDesigner(llm_client=object()).design("Add a feature", _analysis())


def test_code_generator_does_not_emit_placeholder_code_as_success():
    result = CodeGenerator(llm_client=object(), workspace_path=".").generate(_design())

    assert result.compile_success is False
    assert result.diffs == []
    assert result.files_touched == []
    assert any("not implemented" in error for error in result.errors)


def test_code_reviewer_fails_closed_for_unreviewed_implementation():
    report = CodeReviewer(llm_client=object(), workspace_path=".").review(_implementation())

    assert report.approved is False
    assert any("not implemented" in comment for comment in report.comments)


def test_code_reviewer_rejects_failed_implementation():
    implementation = ImplementationResult(
        diffs=[], files_touched=[], compile_success=False, errors=["syntax error"]
    )
    report = CodeReviewer(llm_client=object(), workspace_path=".").review(implementation)

    assert report.approved is False
    assert "syntax error" in report.comments


def test_security_reviewer_never_auto_approves_unreviewed_code():
    with pytest.raises(NotImplementedError, match="no approval was issued"):
        SecurityReviewer(llm_client=object()).review(_implementation().diffs)


def test_dependency_manager_updates_manifest_idempotently_and_rejects_conflicts(tmp_path):
    manifest = tmp_path / "requirements.txt"
    manifest.write_text("pytest>=8\n", encoding="utf-8")
    manager = DependencyManager(str(tmp_path))

    assert manager.add_dependency("Requests >= 2.31") is True
    expected = "pytest>=8\nrequests>=2.31\n"
    assert manifest.read_text(encoding="utf-8") == expected
    assert manager.add_dependency("requests>=2.31") is True
    assert manifest.read_text(encoding="utf-8") == expected
    assert manager.add_dependency("requests<2") is False
    assert manifest.read_text(encoding="utf-8") == expected
    assert manager.add_dependency("requests @ https://example.invalid/pkg.whl") is False
    assert manifest.read_text(encoding="utf-8") == expected


def test_dependency_manager_does_not_claim_success_without_manifest(tmp_path):
    assert DependencyManager(str(tmp_path)).add_dependency("requests>=2") is False


def test_documentation_engine_does_not_silently_claim_to_update_docs():
    with pytest.raises(NotImplementedError, match="no documentation was changed"):
        DocumentationEngine(llm_client=object(), workspace_path=".").document_changes(
            ImplementationResult(diffs=[], files_touched=[], compile_success=True), _analysis()
        )


def test_refactoring_engine_returns_failure_when_it_does_not_refactor():
    result = RefactoringEngine(llm_client=object(), workspace_path=".").refactor("module.py", _analysis())

    assert result.compile_success is False
    assert result.diffs == []
    assert result.files_touched == []
    assert any("not implemented" in error for error in result.errors)


def test_release_manager_does_not_fabricate_release_information():
    with pytest.raises(NotImplementedError, match="no release data was fabricated"):
        ReleaseManager(llm_client=object()).generate_release("abc123", "def456")
