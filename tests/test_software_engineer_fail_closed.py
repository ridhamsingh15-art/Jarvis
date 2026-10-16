import pytest

from applications.software_engineer.architecture_designer import ArchitectureDesigner
from applications.software_engineer.code_generator import CodeGenerator
from applications.software_engineer.code_reviewer import CodeReviewer
from applications.software_engineer.models import (
    ArchitectureDesign,
    CodeDiff,
    ComponentDesign,
    DependencyGraph,
    ImplementationResult,
    RepositoryAnalysis,
)
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
