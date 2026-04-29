"""
SCRIPTS_INVENTORY - List all scripts with signatures and descriptions (XML)

Outputs a structured XML document with all scripts in the workspace:
- path, kind (as attributes when present)
- summary / description (only when non-empty)
- signature (derived from JSON schema when present)

Notes:
- Uses Windmill REST API via BASE_INTERNAL_URL/BASE_URL + WM_WORKSPACE + WM_TOKEN.
- Uses /scripts/list_paths to ensure it lists all scripts.
"""

from __future__ import annotations

import os
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _non_empty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s if s else None


def _get_api_base_url() -> str:
    base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
    if not base_url:
        raise RuntimeError("Missing BASE_INTERNAL_URL/BASE_URL env var")
    base_url = base_url.rstrip("/")
    if base_url.endswith("/api"):
        return base_url
    return f"{base_url}/api"


def _get_workspace() -> str:
    ws = os.environ.get("WM_WORKSPACE")
    if not ws:
        raise RuntimeError("Missing WM_WORKSPACE env var")
    return ws


def _get_token() -> str:
    token = os.environ.get("WM_TOKEN") or os.environ.get("TOKEN")
    if not token:
        raise RuntimeError("Missing WM_TOKEN env var")
    return token


def _api_get_any(
    api_base: str,
    token: str,
    path: str,
    *,
    timeout_s: int = 60,
) -> Any:
    url = f"{api_base}{path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout_s)
    if resp.status_code >= 400:
        body = resp.text
        if len(body) > 2000:
            body = body[:2000] + "…"
        raise requests.HTTPError(
            f"{resp.status_code} Error for {resp.request.method} {resp.url}: {body}",
            response=resp,
        )
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        import json

        return json.loads(resp.text)


def _schema_param_type(prop: dict[str, Any]) -> str | None:
    t = prop.get("type")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        # e.g. ["string","null"]
        return "|".join([x for x in t if isinstance(x, str)])
    return None


def _signature_from_schema(schema: dict[str, Any]) -> str | None:
    if not isinstance(schema, dict):
        return None
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    required = schema.get("required")
    req_set = set(required) if isinstance(required, list) else set()

    parts: list[str] = []
    for name in sorted(props.keys()):
        prop = props.get(name)
        if not isinstance(prop, dict):
            continue
        ptype = _schema_param_type(prop)
        default = prop.get("default", None)
        is_required = name in req_set

        s = name
        if ptype:
            s += f": {ptype}"
        if not is_required:
            s += "?"
        if default is not None:
            # keep short; JSON schema defaults can be objects
            if isinstance(default, (str, int, float, bool)) or default is None:
                s += f" = {default!r}"
            else:
                s += " = <default>"
        parts.append(s)

    if not parts:
        return None
    return "main(" + ", ".join(parts) + ")"


def _attrs(attrs: dict[str, Any]) -> str:
    out: list[str] = []
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, str):
            s = v.strip()
            if not s:
                continue
            out.append(f' {k}="{_xml_escape(s)}"')
        else:
            out.append(f' {k}="{_xml_escape(str(v))}"')
    return "".join(out)


def main(
    prefer_draft: bool = True,
    concurrency: int = 8,
    include_schema: bool = True,
) -> str:
    """
    @param prefer_draft If true, try draft version first (falls back to published). Default: true.
    @param concurrency Parallelism for fetching scripts. Default: 8.
    @param include_schema If true, include signature derived from JSON schema. Default: true.
    @return XML string
    """
    if concurrency < 1:
        concurrency = 1

    api_base = _get_api_base_url()
    workspace = _get_workspace()
    token = _get_token()

    paths = _api_get_any(api_base, token, f"/w/{workspace}/scripts/list_paths")
    if not isinstance(paths, list):
        raise RuntimeError("scripts/list_paths did not return a list")
    script_paths = sorted([p for p in paths if isinstance(p, str) and p.strip()])

    def fetch_script(path: str) -> dict[str, Any]:
        encoded = quote(path, safe="/")
        if prefer_draft:
            try:
                return _api_get_any(api_base, token, f"/w/{workspace}/scripts/get/draft/{encoded}")
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (400, 404):
                    pass
                else:
                    raise
        return _api_get_any(api_base, token, f"/w/{workspace}/scripts/get/p/{encoded}")

    scripts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        it = iter(script_paths)
        in_flight: dict[Any, str] = {}

        def submit_next() -> None:
            try:
                p = next(it)
            except StopIteration:
                return
            in_flight[pool.submit(fetch_script, p)] = p

        for _ in range(concurrency):
            submit_next()

        while in_flight:
            done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                p = in_flight.pop(fut)
                try:
                    obj = fut.result()
                    if isinstance(obj, dict):
                        scripts.append(obj)
                    else:
                        scripts.append({"path": p, "_error": "non-object response"})
                except Exception as exc:  # noqa: BLE001
                    scripts.append({"path": p, "_error": str(exc)})
                submit_next()

    scripts.sort(key=lambda x: str(x.get("path", "")))

    generated_at = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append(f'<scripts generated_at="{_xml_escape(generated_at)}" workspace="{_xml_escape(workspace)}">')

    for s in scripts:
        path = _non_empty_str(s.get("path"))
        if not path:
            continue

        attrs = {
            "path": path,
            "kind": _non_empty_str(s.get("kind")),
        }
        lines.append(f"  <script{_attrs(attrs)}>")

        summary = _non_empty_str(s.get("summary"))
        if summary:
            lines.append(f"    <summary>{_xml_escape(summary)}</summary>")

        description = _non_empty_str(s.get("description"))
        if description:
            lines.append(f"    <description>{_xml_escape(description)}</description>")

        if include_schema:
            signature = _signature_from_schema(s.get("schema") or {})
            if signature:
                lines.append(f"    <signature>{_xml_escape(signature)}</signature>")

        err = _non_empty_str(s.get("_error"))
        if err:
            lines.append(f"    <error>{_xml_escape(err)}</error>")

        lines.append("  </script>")

    lines.append("</scripts>")
    return "\n".join(lines)
