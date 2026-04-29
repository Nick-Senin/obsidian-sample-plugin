"""
TODO_AUDIT - Поиск TODO в description у scripts/flows/apps через Windmill API

ЧТО ДЕЛАЕТ:
- Получает из Windmill API список scripts/flows/apps (с пагинацией)
- Для scripts/flows: сканирует все поля с ключом `description` / `summary` в полученном объекте
- Для apps: дополнительно запрашивает полный app spec и сканирует все `description` / `summary` в нем
- Ищет строки, содержащие `TODO` (по умолчанию case-insensitive)
- Возвращает JSON summary + список найденных совпадений
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Iterable
from urllib.parse import quote

import requests


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


def _api_get(
    api_base: str,
    token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_s: int = 60,
    max_retries: int = 3,
    retry_sleep_s: float = 0.6,
) -> Any:
    url = f"{api_base}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout_s)
            if resp.status_code >= 400:
                # make debugging much easier for 4xx/5xx (Windmill often returns JSON error bodies)
                body = resp.text
                if len(body) > 2000:
                    body = body[:2000] + "…"
                raise requests.HTTPError(
                    f"{resp.status_code} Error for {resp.request.method} {resp.url}: {body}",
                    response=resp,
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(retry_sleep_s * attempt)
    raise last_exc  # pragma: no cover


def _api_get_any(
    api_base: str,
    token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_s: int = 60,
    max_retries: int = 3,
    retry_sleep_s: float = 0.6,
) -> Any:
    """
    Like _api_get, but parses JSON even if content-type isn't application/json.
    Useful for endpoints returning JSON with text/plain content-type.
    """
    url = f"{api_base}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout_s)
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
                return json.loads(resp.text)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(retry_sleep_s * attempt)
    raise last_exc  # pragma: no cover


def _normalize_query_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, bool):
            # backend expects 'true'/'false' (Python would otherwise serialize to 'True'/'False')
            normalized[k] = "true" if v else "false"
        else:
            normalized[k] = v
    return normalized


def _iter_description_strings(obj: Any, pointer: str = "") -> Iterable[tuple[str, str]]:
    """
    Yields (json_pointer, text) for any dict key in {'description', 'summary'}.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_ptr = f"{pointer}/{key}" if pointer else f"/{key}"
            if key in {"description", "summary"} and isinstance(value, str):
                yield (child_ptr, value)
            yield from _iter_description_strings(value, child_ptr)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            child_ptr = f"{pointer}/{idx}" if pointer else f"/{idx}"
            yield from _iter_description_strings(value, child_ptr)


def _find_todo_lines(text: str, todo_re: re.Pattern[str]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if todo_re.search(line):
            hits.append(
                {
                    "line_no": line_no,
                    "line": line.strip(),
                }
            )
    return hits


def _paginate(
    api_base: str,
    token: str,
    workspace: str,
    endpoint: str,
    *,
    per_page: int,
    extra_params: dict[str, Any] | None = None,
) -> Iterable[Any]:
    # Some backend versions are stricter about query params (unknown params / max per_page).
    # We probe on page=1, then reuse the working combination.
    per_page_candidates = [per_page]
    if per_page > 30:
        per_page_candidates.append(30)
    per_page_candidates.append(20)

    extra_variants: list[dict[str, Any]] = []
    base_extra = dict(extra_params or {})
    extra_variants.append(base_extra)
    for key in ["show_archived", "include_draft_only", "order_desc"]:
        if key in base_extra:
            v = dict(base_extra)
            v.pop(key, None)
            extra_variants.append(v)
    if base_extra:
        extra_variants.append({})

    effective_extra: dict[str, Any] | None = None
    effective_per_page: int | None = None

    page = 1
    while True:
        if effective_extra is None or effective_per_page is None:
            last_err: Exception | None = None
            items = None
            for pp in per_page_candidates:
                for ev in extra_variants:
                    try:
                        params = _normalize_query_params({"page": page, "per_page": pp, **ev})
                        items = _api_get(api_base, token, f"/w/{workspace}{endpoint}", params=params)
                        effective_extra = ev
                        effective_per_page = pp
                        break
                    except requests.HTTPError as exc:
                        last_err = exc
                        # try next variant only for 400; other errors should bubble up
                        if exc.response is not None and exc.response.status_code == 400:
                            continue
                        raise
                if items is not None:
                    break
            if items is None:
                raise last_err or RuntimeError(f"Failed to paginate {endpoint}")
        else:
            params = _normalize_query_params(
                {"page": page, "per_page": effective_per_page, **effective_extra}
            )
            items = _api_get(api_base, token, f"/w/{workspace}{endpoint}", params=params)

        if not items:
            return
        for item in items:
            yield item
        page += 1


def main(
    todo_pattern: str = r"\bTODO\b",
    case_insensitive: bool = True,
    per_page: int = 100,
    max_hits: int = 2000,
    include_archived: bool = True,
    include_draft_only: bool = True,
    prefer_draft: bool = True,
    exclude_self: bool = True,
    scripts_concurrency: int = 6,
    flows_concurrency: int = 6,
    apps_concurrency: int = 6,
) -> dict:
    """
    Ищет TODO в `description` у scripts/flows/apps через Windmill API.

    @param todo_pattern Regex-паттерн для поиска TODO (default: \\bTODO\\b)
    @param case_insensitive Если True — поиск без учета регистра (default: True)
    @param per_page Размер страницы для API list endpoints (1..100, default: 100)
    @param max_hits Максимум найденных строк (>=1, default: 2000)
    @param include_archived Включать archived scripts/flows (default: True; на apps не влияет)
    @param include_draft_only Включать draft-only сущности (default: True)
    @param prefer_draft Если true — при наличии draft сканировать draft-версию (default: True)
    @param exclude_self Если true — исключить этот audit-скрипт из результатов (default: True)
    @param scripts_concurrency Параллелизм загрузки scripts (>=1, default: 6)
    @param flows_concurrency Параллелизм загрузки flows (>=1, default: 6)
    @param apps_concurrency Параллелизм при загрузке app spec по пути (>=1, default: 6)
    """
    if per_page < 1:
        per_page = 1
    if per_page > 100:
        per_page = 100
    if max_hits < 1:
        max_hits = 1
    if scripts_concurrency < 1:
        scripts_concurrency = 1
    if flows_concurrency < 1:
        flows_concurrency = 1
    if apps_concurrency < 1:
        apps_concurrency = 1

    api_base = _get_api_base_url()
    workspace = _get_workspace()
    token = _get_token()

    flags = re.IGNORECASE if case_insensitive else 0
    todo_re = re.compile(todo_pattern, flags=flags)

    excluded_paths = set()
    if exclude_self:
        excluded_paths.add("f/shared/todo_audit/scan_todos_in_descriptions")

    summary: dict[str, Any] = {
        "todo_pattern": todo_pattern,
        "case_insensitive": case_insensitive,
        "api_base": api_base,
        "workspace": workspace,
        "scanned": {"scripts": 0, "flows": 0, "apps": 0},
        "with_todo": {"scripts": 0, "flows": 0, "apps": 0},
        "occurrences": {"scripts": 0, "flows": 0, "apps": 0},
        "truncated": False,
    }
    results: list[dict[str, Any]] = []

    def add_hits(kind: str, entity_path: str, entity_id: Any, desc_ptr: str, hits: list[dict[str, Any]]) -> None:
        nonlocal results
        if not hits:
            return
        if len(results) >= max_hits:
            summary["truncated"] = True
            return
        for h in hits:
            if len(results) >= max_hits:
                summary["truncated"] = True
                return
            results.append(
                {
                    "kind": kind,
                    "path": entity_path,
                    "id": entity_id,
                    "description_pointer": desc_ptr,
                    "line_no": h["line_no"],
                    "line": h["line"],
                }
            )

    # scripts
    script_list: list[dict[str, Any]] = []
    script_paths_ok = False
    try:
        paths = _api_get_any(api_base, token, f"/w/{workspace}/scripts/list_paths")
        if isinstance(paths, list):
            script_paths_ok = True
            script_list = [{"path": p} for p in paths if isinstance(p, str) and p]
    except Exception:  # noqa: BLE001
        script_list = []

    if not script_paths_ok:
        script_params: dict[str, Any] = {
            "show_archived": include_archived,
            "include_draft_only": include_draft_only,
            "order_desc": False,
        }
        for item in _paginate(api_base, token, workspace, "/scripts/list", per_page=per_page, extra_params=script_params):
            if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("path"):
                script_list.append(item)

    def fetch_script(item: dict[str, Any]) -> dict[str, Any]:
        path = item["path"]
        encoded = quote(path, safe="/")
        if prefer_draft:
            try:
                return _api_get(api_base, token, f"/w/{workspace}/scripts/get/draft/{encoded}")
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (400, 404):
                    pass
                else:
                    raise
        return _api_get(api_base, token, f"/w/{workspace}/scripts/get/p/{encoded}")

    with ThreadPoolExecutor(max_workers=scripts_concurrency) as pool:
        it = iter(script_list)
        in_flight: dict[Any, dict[str, Any]] = {}

        def submit_next() -> None:
            if summary["truncated"]:
                return
            try:
                item = next(it)
            except StopIteration:
                return
            in_flight[pool.submit(fetch_script, item)] = item

        for _ in range(scripts_concurrency):
            submit_next()

        while in_flight and not summary["truncated"]:
            done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                item = in_flight.pop(fut)
                if summary["truncated"]:
                    continue
                try:
                    script = fut.result()
                except Exception as exc:  # noqa: BLE001
                    add_hits(
                        "script",
                        item.get("path"),
                        item.get("hash"),
                        "/_error",
                        [{"line_no": 0, "line": f"ERROR: failed to fetch script: {exc}"}],
                    )
                    submit_next()
                    continue

                if script.get("path") in excluded_paths:
                    submit_next()
                    continue

                summary["scanned"]["scripts"] += 1
                entity_has_todo = False
                for desc_ptr, desc_text in _iter_description_strings(script):
                    hits = _find_todo_lines(desc_text, todo_re)
                    if hits:
                        entity_has_todo = True
                        summary["occurrences"]["scripts"] += len(hits)
                        add_hits("script", script.get("path"), script.get("hash"), desc_ptr, hits)
                if entity_has_todo:
                    summary["with_todo"]["scripts"] += 1

                submit_next()

    # flows
    if not summary["truncated"]:
        flow_params: dict[str, Any] = {
            "show_archived": include_archived,
            "include_draft_only": include_draft_only,
            "order_desc": False,
        }
        flow_list: list[dict[str, Any]] = []
        flow_paths_ok = False
        try:
            paths = _api_get_any(api_base, token, f"/w/{workspace}/flows/list_paths")
            if isinstance(paths, list):
                flow_paths_ok = True
                flow_list = [{"path": p} for p in paths if isinstance(p, str) and p]
        except Exception:  # noqa: BLE001
            flow_list = []

        if not flow_paths_ok:
            for item in _paginate(api_base, token, workspace, "/flows/list", per_page=per_page, extra_params=flow_params):
                if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("path"):
                    flow_list.append(item)

        def fetch_flow(item: dict[str, Any]) -> dict[str, Any]:
            path = item["path"]
            encoded = quote(path, safe="/")
            if prefer_draft:
                try:
                    return _api_get(api_base, token, f"/w/{workspace}/flows/get/draft/{encoded}")
                except requests.HTTPError as exc:
                    if exc.response is not None and exc.response.status_code in (400, 404):
                        pass
                    else:
                        raise
            return _api_get(api_base, token, f"/w/{workspace}/flows/get/{encoded}")

        with ThreadPoolExecutor(max_workers=flows_concurrency) as pool:
            it = iter(flow_list)
            in_flight = {}

            def submit_next() -> None:
                if summary["truncated"]:
                    return
                try:
                    item = next(it)
                except StopIteration:
                    return
                in_flight[pool.submit(fetch_flow, item)] = item

            for _ in range(flows_concurrency):
                submit_next()

            while in_flight and not summary["truncated"]:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    item = in_flight.pop(fut)
                    if summary["truncated"]:
                        continue
                    try:
                        flow = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        add_hits(
                            "flow",
                            item.get("path"),
                            None,
                            "/_error",
                            [{"line_no": 0, "line": f"ERROR: failed to fetch flow: {exc}"}],
                        )
                        submit_next()
                        continue

                    if flow.get("path") in excluded_paths:
                        submit_next()
                        continue

                    summary["scanned"]["flows"] += 1
                    entity_has_todo = False
                    for desc_ptr, desc_text in _iter_description_strings(flow):
                        hits = _find_todo_lines(desc_text, todo_re)
                        if hits:
                            entity_has_todo = True
                            summary["occurrences"]["flows"] += len(hits)
                            add_hits("flow", flow.get("path"), None, desc_ptr, hits)
                    if entity_has_todo:
                        summary["with_todo"]["flows"] += 1

                    submit_next()

    # apps (need full spec)
    if not summary["truncated"]:
        app_params: dict[str, Any] = {
            "include_draft_only": include_draft_only,
            "order_desc": False,
        }

        def fetch_app(app_path: str) -> tuple[str, Any] | None:
            encoded = quote(app_path, safe="/")
            if prefer_draft:
                try:
                    obj = _api_get(api_base, token, f"/w/{workspace}/apps/get/draft/{encoded}")
                    return (app_path, obj)
                except requests.HTTPError as exc:
                    if exc.response is not None and exc.response.status_code in (400, 404):
                        pass
                    else:
                        raise
            obj = _api_get(api_base, token, f"/w/{workspace}/apps/get/p/{encoded}")
            return (app_path, obj)

        app_paths: list[str] = []
        for app in _paginate(api_base, token, workspace, "/apps/list", per_page=per_page, extra_params=app_params):
            path = app.get("path")
            if isinstance(path, str) and path:
                app_paths.append(path)

        with ThreadPoolExecutor(max_workers=max(1, apps_concurrency)) as pool:
            it = iter(app_paths)
            in_flight: dict[Any, str] = {}

            def submit_next() -> None:
                if summary["truncated"]:
                    return
                try:
                    p = next(it)
                except StopIteration:
                    return
                in_flight[pool.submit(fetch_app, p)] = p

            for _ in range(max(1, apps_concurrency)):
                submit_next()

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    app_path = in_flight.pop(fut)
                    if summary["truncated"]:
                        continue
                    try:
                        _, app_obj = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        add_hits(
                            "app",
                            app_path,
                            None,
                            "/_error",
                            [{"line_no": 0, "line": f"ERROR: failed to fetch app: {exc}"}],
                        )
                        submit_next()
                        continue

                    if app_obj.get("path", app_path) in excluded_paths:
                        submit_next()
                        continue

                    summary["scanned"]["apps"] += 1
                    entity_has_todo = False
                    for desc_ptr, desc_text in _iter_description_strings(app_obj):
                        hits = _find_todo_lines(desc_text, todo_re)
                        if hits:
                            entity_has_todo = True
                            summary["occurrences"]["apps"] += len(hits)
                            add_hits("app", app_obj.get("path", app_path), app_obj.get("id"), desc_ptr, hits)
                    if entity_has_todo:
                        summary["with_todo"]["apps"] += 1
                    submit_next()

            # best-effort cancel any remaining tasks if we truncated early
            if summary["truncated"]:
                for fut in list(in_flight.keys()):
                    fut.cancel()

    return {"summary": summary, "items": results}
