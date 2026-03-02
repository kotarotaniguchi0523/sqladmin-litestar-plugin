from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar import Litestar

from sqladmin_litestar_plugin import (
    PathFixMiddleware,
    SQLAdminPlugin,
    _prepare_scope,  # noqa: PLC2701
)

if TYPE_CHECKING:
    from litestar.types.asgi_types import Receive, Scope, Send


@pytest.fixture(name="plugin")
def plugin_fixture() -> SQLAdminPlugin:
    return SQLAdminPlugin()


@pytest.fixture(name="app")
def app_fixture(plugin: SQLAdminPlugin) -> Litestar:
    return Litestar(plugins=[plugin], openapi_config=None)


def test_starlette_app_redirects_disabled(plugin: SQLAdminPlugin) -> None:
    assert plugin.admin.admin.router.redirect_slashes is False
    assert plugin.starlette_app.router.redirect_slashes is False


def test_views_added_to_admin_app(plugin: SQLAdminPlugin, monkeypatch: pytest.MonkeyPatch) -> None:
    mock = MagicMock()
    monkeypatch.setattr(plugin.admin, "add_view", mock)
    plugin.views = [MagicMock()]
    Litestar(plugins=[plugin], openapi_config=None)
    mock.assert_called_once_with(plugin.views[0])


@pytest.mark.parametrize("should_raise", [True, False])
@pytest.mark.anyio
async def test_resets_app_in_scope(
    *, should_raise: bool, plugin: SQLAdminPlugin, app: Litestar, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = MagicMock(side_effect=RuntimeError if should_raise else None)

    async def fake_admin_app(scope: Scope, _: Receive, __: Send) -> None:  # noqa: RUF029
        scope["app"] = "admin"  # type: ignore[arg-type]
        mock()

    monkeypatch.setattr(plugin, "starlette_app", fake_admin_app)
    handler = app.route_handler_method_map["/admin"]["asgi"].fn
    fake_scope = {"app": app, "path": "/"}

    if should_raise:
        with pytest.raises(RuntimeError):
            await handler(fake_scope, MagicMock(), MagicMock())
    else:
        await handler(fake_scope, MagicMock(), MagicMock())
    assert fake_scope["app"] == app
    mock.assert_called_once()


@pytest.mark.parametrize("should_raise", [True, False])
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/admin", "/admin/"),
        ("/admin/", "/admin/"),
        ("/admin/other", "/admin/other"),
        ("/admin/other/", "/admin/other"),
        ("admin", "/admin/"),
        ("admin/", "/admin/"),
        ("admin/other", "/admin/other"),
        ("admin/other/", "/admin/other"),
    ],
)
@pytest.mark.anyio
async def test_path_fix_middleware(path: str, expected: str, *, should_raise: bool) -> None:
    from starlette.types import Receive, Scope, Send  # noqa: PLC0415, F401

    async def app(scope: Scope, _: Receive, send: Send) -> None:
        assert scope["path"] == expected
        assert scope["raw_path"] == expected.encode("utf-8")
        if should_raise:
            raise RuntimeError
        await send(MagicMock())

    middleware = PathFixMiddleware(app, base_url="/admin")
    fake_scope = {"path": path, "raw_path": path.encode("utf-8")}

    if should_raise:
        with pytest.raises(RuntimeError):
            await middleware(fake_scope, MagicMock(), MagicMock())
    else:
        await middleware(fake_scope, MagicMock(), AsyncMock())

    assert fake_scope["path"] == path
    assert fake_scope["raw_path"] == path.encode("utf-8")


@pytest.mark.parametrize(
    "base_url",
    [
        "admin",
        "//evil.com",
        "/../secret",
        "/admin/../secret",
        "/admin/./here",
    ],
)
def test_base_url_validation_rejects_invalid(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        SQLAdminPlugin(base_url=base_url)


@pytest.mark.parametrize("base_url", ["/admin", "/my-admin/panel"])
def test_base_url_validation_accepts_valid(base_url: str) -> None:
    plugin = SQLAdminPlugin(base_url=base_url)
    assert plugin.admin.base_url == base_url


@pytest.mark.anyio
async def test_path_fix_middleware_preserves_raw_path_encoding() -> None:
    from starlette.types import Receive, Scope, Send  # noqa: PLC0415, F401

    async def app(scope: Scope, _: Receive, send: Send) -> None:
        assert scope["raw_path"] == b"/admin/hello%20world"
        await send(MagicMock())

    middleware = PathFixMiddleware(app, base_url="/admin")
    fake_scope = {"path": "/admin/hello world", "raw_path": b"/admin/hello%20world"}

    await middleware(fake_scope, MagicMock(), AsyncMock())

    assert fake_scope["raw_path"] == b"/admin/hello%20world"


def test_prepare_scope_isolates_state() -> None:
    original_state = {"user": "alice"}
    scope = {"path": "/list", "state": original_state, "headers": [(b"host", b"localhost")]}

    copied = _prepare_scope(scope, "/admin")

    copied["state"]["injected"] = True
    copied["headers"].append((b"x-extra", b"value"))

    assert "injected" not in original_state
    assert len(scope["headers"]) == 1
