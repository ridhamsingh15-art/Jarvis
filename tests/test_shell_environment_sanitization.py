import sys

from tools.shell import ShellTool, _is_sensitive_environment_key


def test_sensitive_environment_key_patterns_cover_common_provider_secrets():
    sensitive = (
        "AWS_ACCESS_KEY_ID",
        "AZURE_CLIENT_SECRET",
        "HF_TOKEN",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "CUSTOM_SERVICE_PASSWORD",
        "CUSTOM_SIGNING_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AWS_PROFILE",
        "KUBECONFIG",
        "SSH_AUTH_SOCK",
    )
    for key in sensitive:
        assert _is_sensitive_environment_key(key), key

    assert not _is_sensitive_environment_key("PATH")
    assert not _is_sensitive_environment_key("SYSTEMROOT")
    assert not _is_sensitive_environment_key("PYTHONUTF8")


def test_shell_child_process_never_receives_common_secret_values(monkeypatch, tmp_path):
    variables = {
        "AWS_ACCESS_KEY_ID": "aws-access-must-not-leak",
        "AZURE_CLIENT_SECRET": "azure-client-must-not-leak",
        "HF_TOKEN": "hf-token-must-not-leak",
        "CUSTOM_SERVICE_PASSWORD": "password-must-not-leak",
        "CUSTOM_SIGNING_KEY": "signing-key-must-not-leak",
        "GITHUB_PERSONAL_ACCESS_TOKEN": "github-token-must-not-leak",
    }
    for key, value in variables.items():
        monkeypatch.setenv(key, value)

    keys = ",".join(repr(key) for key in variables)
    script = f"import os; print(','.join(os.getenv(k, 'NOT_FOUND') for k in [{keys}]))"
    result = ShellTool(workspace_root=tmp_path).run(f'"{sys.executable}" -c "{script}"')

    assert result.success, result.stderr
    assert result.stdout.strip() == ",".join(["NOT_FOUND"] * len(variables))
    for value in variables.values():
        assert value not in result.stdout
