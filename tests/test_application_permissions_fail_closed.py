import pytest

from core.applications.exceptions import AppPermissionError
from core.applications.models import AppManifest
from core.applications.permissions import AppPermissionManager
from core.models.primitives import Identifier
from core.plugins.permissions import PermissionManager


def _manifest(required_permissions: list[str]) -> AppManifest:
    return AppManifest(
        id="sample-app",
        name="Sample app",
        version="1.0.0",
        description="test manifest",
        entry_point="main.py",
        required_permissions=required_permissions,
    )


def test_permission_manager_denies_without_backend():
    manager = AppPermissionManager(object())

    assert manager.check_permission("sample-app", "filesystem") is False
    with pytest.raises(AppPermissionError, match="lacks permission"):
        manager.assert_permission("sample-app", "filesystem")
    with pytest.raises(AppPermissionError, match="backend is unavailable"):
        manager.grant_permissions(_manifest(["filesystem"]))


def test_permission_request_does_not_implicitly_grant_access():
    core_manager = PermissionManager()
    manager = AppPermissionManager(core_manager)

    with pytest.raises(AppPermissionError, match="user-approved permissions"):
        manager.grant_permissions(_manifest(["network"]))

    assert core_manager.has_permission(Identifier("sample-app"), "network") is False
    assert manager.check_permission("sample-app", "network") is False


def test_explicit_core_grant_allows_permission_verification():
    core_manager = PermissionManager()
    app_id = Identifier("sample-app")
    core_manager.grant(app_id, "network")
    manager = AppPermissionManager(core_manager)

    manager.grant_permissions(_manifest(["network"]))
    assert manager.check_permission("sample-app", "network") is True


def test_permissionless_application_does_not_need_backend():
    manager = AppPermissionManager(None)
    manager.grant_permissions(_manifest([]))
