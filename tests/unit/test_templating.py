"""Unit tests for ``web/templating.py``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from job_board_scraper.web.templating import _build_query_string, url_for_with_query


class TestBuildQueryString:
    def test_empty(self) -> None:
        assert _build_query_string({}) == ""

    def test_simple(self) -> None:
        assert _build_query_string({"a": "1"}) == "a=1"

    def test_drops_none(self) -> None:
        assert _build_query_string({"a": "1", "b": None}) == "a=1"

    def test_drops_empty_string(self) -> None:
        assert _build_query_string({"a": "1", "b": ""}) == "a=1"

    def test_multiple(self) -> None:
        assert _build_query_string({"a": "1", "b": "2"}) == "a=1&b=2"


class _Route:
    def __init__(self, name: str, path_format: str) -> None:
        self.name = name
        self.path_format = path_format


class _Router:
    def __init__(self, routes: list[_Route]) -> None:
        self.routes = routes


class TestUrlForWithQuery:
    def _request(self) -> MagicMock:
        request = MagicMock()
        request.url_for.return_value = "/"
        return request

    def test_unknown_route_falls_back_to_starlette(self) -> None:
        request = self._request()
        request.scope = {"router": _Router([])}
        # Starlette default: url_for raises NoMatchFound.
        request.url_for.side_effect = Exception("NoMatchFound")
        with pytest.raises(Exception):
            url_for_with_query({"request": request}, "missing")

    def test_known_route_appends_query_string(self) -> None:
        request = self._request()
        request.scope = {"router": _Router([_Route("home", "/")])}
        result = url_for_with_query({"request": request}, "home", x="1", y="2")
        assert result == "/?x=1&y=2"

    def test_known_route_drops_none_and_empty(self) -> None:
        request = self._request()
        request.scope = {"router": _Router([_Route("home", "/")])}
        result = url_for_with_query(
            {"request": request}, "home", x="1", y=None, z=""
        )
        assert result == "/?x=1"

    def test_route_with_path_param_passes_through(self) -> None:
        request = self._request()
        request.scope = {
            "router": _Router([_Route("show_run", "/runs/{run_id}")])
        }
        # request.url_for called with path params only
        def _fake_url_for(name, **kwargs):
            assert name == "show_run"
            assert kwargs == {"run_id": 7}
            return "/runs/7"

        request.url_for.side_effect = _fake_url_for
        result = url_for_with_query(
            {"request": request}, "show_run", run_id=7, page=2
        )
        assert result == "/runs/7?page=2"

    def test_finds_route_in_nested_mount(self) -> None:
        """_route_path_params should look into Mount routers."""
        class _Mount(_Route):
            def __init__(self) -> None:
                self.name = "outer_mount"
                self.path_format = None  # mount routes don't have path_format
                self.routes = [_Route("inner", "/inner/{x}")]

        class _OuterRouter(_Router):
            pass

        # Manually populate routes instead of base class to include the mount.
        outer = _OuterRouter([])
        outer.routes = [_Mount()]

        request = self._request()
        request.scope = {"router": outer}
        params = _route_path_params(
            request.scope, "inner"
        )
        assert params == {"x"}


def _route_path_params(scope, name):
    """Local import to avoid module-level cycle in test."""
    from job_board_scraper.web.templating import _route_path_params as fn

    return fn(scope, name)
