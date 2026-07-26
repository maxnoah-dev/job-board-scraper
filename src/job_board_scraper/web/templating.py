"""Jinja helpers shared across the web dashboard.

Currently this module exposes a single helper, :func:`url_for_with_query`,
which is installed as the Jinja ``url_for`` global. It mirrors Starlette's
``Request.url_for`` but accepts arbitrary keyword arguments and routes the
ones the target route does not consume as path parameters through to the
URL's query string.

Why this is needed: Starlette's default ``url_for`` helper raises
``NoMatchFound`` whenever a template passes a keyword argument that is
not declared as a path parameter on the matched route. Pagination links
in our templates need to send the ``page`` query parameter along with
filters, so the default behaviour 500s the moment a list view renders
its pagination block.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

from jinja2 import pass_context
from starlette.requests import Request
from starlette.types import Scope


def _route_path_params(scope: Scope, name: str) -> set[str] | None:
    """Return the set of path-param names declared on the route named ``name``.

    Returns ``None`` if no route with that name is registered so the caller
    can fall back to Starlette's behaviour (which will raise the usual
    ``NoMatchFound`` error).
    """
    router = scope.get("router") or scope.get("app")
    if router is None:  # pragma: no cover - defensive: only happens outside ASGI
        return None

    for route in router.routes:
        # A bare ``Route`` exposes its own path params; APIRoute wraps it.
        path_format = getattr(route, "path_format", None)
        route_name = getattr(route, "name", None)
        if path_format is None or route_name != name:
            continue
        # ``path_format`` looks like "/runs/{run_id}" — strip the braces.
        params: set[str] = set()
        segment = ""
        depth = 0
        for char in path_format:
            if char == "{":
                depth += 1
                segment = ""
            elif char == "}":
                if depth == 1:
                    params.add(segment)
                depth = max(depth - 1, 0)
                segment = ""
            elif depth >= 1:
                segment += char
        return params

    # Some routes (notably ``Mount``) wrap child routers. Recurse one level
    # so URLs for nested mounts still resolve.
    for route in router.routes:
        child_routes = getattr(route, "routes", None)
        if not child_routes:
            continue
        for child in child_routes:
            if getattr(child, "name", None) != name:
                continue
            path_format = getattr(child, "path_format", None)
            if path_format is None:
                continue
            params: set[str] = set()
            segment = ""
            depth = 0
            for char in path_format:
                if char == "{":
                    depth += 1
                    segment = ""
                elif char == "}":
                    if depth == 1:
                        params.add(segment)
                    depth = max(depth - 1, 0)
                    segment = ""
                elif depth >= 1:
                    segment += char
            return params
    return None


def _build_query_string(params: Mapping[str, Any]) -> str:
    """Encode ``params`` as a URL-encoded query string.

    ``None`` and empty-string values are dropped to keep URLs clean.
    Non-scalar values are coerced with ``str()`` because Jinja templates
    occasionally forward pre-formatted strings already.
    """
    encoded_pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None or value == "":
            continue
        encoded_pairs.append((str(key), str(value)))
    if not encoded_pairs:
        return ""
    return urlencode(encoded_pairs, doseq=True)


@pass_context
def url_for_with_query(context: dict[str, Any], name: str, /, **params: Any) -> str:
    """Jinja-friendly ``url_for`` that supports query parameters.

    Parameters that the target route declares as path parameters are passed
    through to Starlette's :meth:`Request.url_for`. Any remaining
    parameters are appended to the resulting URL as a query string. This
    lets templates keep using a familiar ``url_for('list_runs', page=2)``
    syntax even when ``page`` is a query parameter on the route.
    """
    request: Request = context["request"]
    path_params = _route_path_params(request.scope, name)
    if path_params is None:
        # Unknown route — fall back to default behaviour so the original
        # ``NoMatchFound`` error still surfaces for genuine typos.
        return str(request.url_for(name, **params))

    query_params = {k: v for k, v in params.items() if k not in path_params}
    path_kwargs = {k: v for k, v in params.items() if k in path_params}

    base_url = request.url_for(name, **path_kwargs)
    query = _build_query_string(query_params)
    if not query:
        return str(base_url)
    return f"{base_url}?{query}"


__all__ = ["url_for_with_query"]
