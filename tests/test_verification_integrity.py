from mission_control import crash_safe


def test_file_exists_assertion_cannot_verify_an_unrelated_preexisting_file(tmp_path):
    requested = tmp_path / "requested.txt"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("already exists", encoding="utf-8")
    result = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": f"file_exists:{unrelated}"},
        "file", "create_file", {"path": str(requested)}, {}, {"status": "not_supported"},
    )
    assert result["status"] == "failed"
    assert result["expected_outcome_status"] == "failed"

def test_file_contains_assertion_cannot_read_an_unrelated_file(tmp_path):
    requested = tmp_path / "requested.txt"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("secret target phrase", encoding="utf-8")
    result = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": f"file_contains:{unrelated}::target phrase"},
        "file", "write_file", {"path": str(requested)}, {}, {"status": "not_supported"},
    )
    assert result["status"] == "failed"
    assert result["expected_outcome_status"] == "failed"

def test_declared_file_exists_does_not_override_failed_action_verification(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("pre-existing", encoding="utf-8")
    result = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": f"file_exists:{target}"},
        "file", "write_file", {"path": str(target)}, {}, {"status": "failed", "error": "write failed"},
    )
    assert result["status"] == "failed"
    assert result["error"] == "write failed"

def test_declared_file_contains_does_not_override_failed_action_verification(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("expected phrase", encoding="utf-8")
    result = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": f"file_contains:{target}::expected phrase"},
        "file", "write_file", {"path": str(target)}, {}, {"status": "failed", "error": "write failed"},
    )
    assert result["status"] == "failed"
    assert result["error"] == "write failed"

def test_process_assertion_must_match_requested_app_and_preserve_failed_verifier(monkeypatch):
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"notepad.exe"})
    wrong_app = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": "process_running:notepad.exe"},
        "windows", "open_app", {"app": "calculator"}, {}, {"status": "not_supported"},
    )
    assert wrong_app["status"] == "failed"

    failed_action = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": "process_running:notepad.exe"},
        "windows", "open_app", {"app": "notepad"}, {}, {"status": "failed", "error": "launch failed"},
    )
    assert failed_action["status"] == "failed"
    assert failed_action["error"] == "launch failed"

def test_url_assertion_must_match_requested_url_and_preserve_failed_verifier(monkeypatch):
    monkeypatch.setattr(crash_safe, "_cdp_page_urls", lambda: ["https://example.com/page"])
    wrong_request = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": "url_matches:https://example.com/page"},
        "browser", "open_url", {"url": "https://different.example/"}, {}, {"status": "not_supported"},
    )
    assert wrong_request["status"] == "failed"

    failed_action = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": "url_matches:https://example.com/page"},
        "browser", "open_url", {"url": "https://example.com/page"}, {}, {"status": "failed", "error": "navigation failed"},
    )
    assert failed_action["status"] == "failed"
    assert failed_action["error"] == "navigation failed"
