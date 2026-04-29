from __future__ import annotations

import os
from typing import Any, NotRequired, TypedDict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import wmill
from urllib.parse import quote


class baserow(TypedDict):
    """
    Expected keys for the BaserowConfig resource.

    The script is tolerant to a few aliases because Windmill resources may be
    stored either as a plain token string or as a JSON object.
    """

    token: NotRequired[str]
    api_token: NotRequired[str]
    api_key: NotRequired[str]
    base_url: NotRequired[str]
    url: NotRequired[str]
    references_table_id: NotRequired[int]
    table_id: NotRequired[int]


UTM_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
}


def _canonicalize_url(url_raw: str) -> str:
    value = (url_raw or "").strip()
    if not value:
        raise ValueError("url_raw is empty")

    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlsplit(f"https://{value.lstrip('/')}")

    if not parsed.netloc:
        raise ValueError(f"Invalid URL (missing host): {value}")

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_pairs = [(k, v) for (k, v) in query_pairs if k.lower() not in UTM_KEYS]
    query = urlencode(filtered_pairs, doseq=True)

    path = parsed.path or ""
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, query, parsed.fragment))


def _load_resource(path: str) -> Any:
    """
    Prefer interpolated resources to resolve `$var:` references.

    Falls back to non-interpolated `/get_value` only if interpolated is not available.
    """
    try:
        return wmill.get_resource(path)
    except Exception as e:
        if "get_value_interpolated" not in str(e):
            raise

    base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
    workspace = os.environ.get("WM_WORKSPACE")
    token = os.environ.get("WM_TOKEN")
    if not base_url or not workspace or not token:
        raise

    encoded_path = quote(path, safe="/")
    url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _baserow_api_base(base_url: str) -> str:
    value = (base_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("Baserow base_url is empty")

    parsed = urlsplit(value if "://" in value else f"https://{value}")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    path = (parsed.path or "").rstrip("/")

    if netloc.lower() == "baserow.io":
        netloc = "api.baserow.io"
        if path == "/api":
            path = ""

    base = urlunsplit((scheme, netloc, path, "", "")).rstrip("/")
    return base if base.endswith("/api") else f"{base}/api"


def _resolve_references_table_id(base_url: str, token: str, table_name: str = "References") -> int:
    api = _baserow_api_base(base_url)
    headers = _baserow_headers(token)

    workspaces_url = f"{api}/workspaces/"
    resp = requests.get(workspaces_url, headers=headers, timeout=30)
    resp.raise_for_status()
    workspaces_raw = resp.json()
    if isinstance(workspaces_raw, dict) and isinstance(workspaces_raw.get("results"), list):
        workspaces = workspaces_raw["results"]
    else:
        workspaces = workspaces_raw
    if not isinstance(workspaces, list):
        raise ValueError("Unexpected Baserow response for workspaces list")

    wanted = table_name.strip().lower()
    matches: list[tuple[int, str, int, str, int, str]] = []
    # (workspace_id, workspace_name, app_id, app_name, table_id, table_name)

    for workspace in workspaces:
        workspace_id = workspace.get("id")
        workspace_name = str(workspace.get("name") or "")
        if not isinstance(workspace_id, int):
            continue

        apps_url = f"{api}/applications/"
        resp = requests.get(
            apps_url,
            headers=headers,
            params={"workspace_id": workspace_id},
            timeout=30,
        )
        resp.raise_for_status()
        apps_raw = resp.json()
        if isinstance(apps_raw, dict) and isinstance(apps_raw.get("results"), list):
            apps = apps_raw["results"]
        else:
            apps = apps_raw
        if not isinstance(apps, list):
            continue

        for app in apps:
            if str(app.get("type") or "").lower() != "database":
                continue
            app_id = app.get("id")
            app_name = str(app.get("name") or "")
            if not isinstance(app_id, int):
                continue

            tables_url = f"{api}/database/tables/database/{app_id}/"
            resp = requests.get(tables_url, headers=headers, timeout=30)
            resp.raise_for_status()
            tables = resp.json()
            if not isinstance(tables, list):
                continue

            for table in tables:
                t_id = table.get("id")
                t_name = str(table.get("name") or "")
                if isinstance(t_id, int) and t_name.strip().lower() == wanted:
                    matches.append(
                        (workspace_id, workspace_name, app_id, app_name, t_id, t_name)
                    )

    if not matches:
        raise ValueError(f"Baserow table '{table_name}' not found")

    if len(matches) == 1:
        return matches[0][4]

    # Try to disambiguate by preferring apps/groups that look like refbot.
    def score(m: tuple[int, str, int, str, int, str]) -> int:
        _, g_name, _, a_name, _, _ = m
        s = 0
        if "refbot" in a_name.lower():
            s += 2
        if "refbot" in g_name.lower():
            s += 1
        return s

    matches_sorted = sorted(matches, key=score, reverse=True)
    if score(matches_sorted[0]) > score(matches_sorted[1]):
        return matches_sorted[0][4]

    details = "; ".join(
        f"group={gid}({gname}) app={aid}({aname}) table={tid}({tname})"
        for gid, gname, aid, aname, tid, tname in matches_sorted
    )
    raise ValueError(
        f"Multiple '{table_name}' tables found; add table_id to resource. Candidates: {details}"
    )


def _coerce_baserow_settings(baserow: Any) -> tuple[str, str, int]:
    if isinstance(baserow, str):
        ref = baserow.strip()
        if not ref:
            raise ValueError("Baserow table resource is an empty string")
        if ref.startswith("$res:"):
            resolved = _load_resource(ref[len("$res:") :])
            return _coerce_baserow_settings(resolved)
        # Allow passing a resource path directly (useful for API calls),
        # e.g. "u/theatmacreator/refbot_baserow".
        resolved = _load_resource(ref)
        return _coerce_baserow_settings(resolved)

    if not isinstance(baserow, dict):
        raise ValueError("Baserow table resource must be a resource (string or object)")

    token = str(
        (baserow.get("token") or baserow.get("api_token") or baserow.get("api_key") or "")
    ).strip()
    if token.startswith("$var:"):
        token = str(wmill.get_variable(token[len("$var:") :])).strip()
    base_url = str((baserow.get("base_url") or baserow.get("url") or "")).strip().rstrip("/")
    if base_url.endswith("/api"):
        base_url = base_url[: -len("/api")]
    parsed = urlsplit(base_url if "://" in base_url else f"https://{base_url}")
    if parsed.netloc.lower() in {"baserow.io", "www.baserow.io"}:
        base_url = urlunsplit((parsed.scheme or "https", "api.baserow.io", parsed.path.rstrip("/"), "", "")).rstrip("/")
    table_id_raw = baserow.get("table_id") or baserow.get("references_table_id")

    if not token:
        raise ValueError("Baserow token is missing (expected baserow_table.token/api_token/api_key)")
    if not base_url:
        raise ValueError("Baserow base_url is missing (expected baserow_table.base_url/url)")
    if table_id_raw is None:
        table_id = _resolve_references_table_id(base_url, token, table_name="References")
        return base_url, token, table_id

    try:
        table_id = int(table_id_raw)
    except Exception as e:  # noqa: BLE001
        raise ValueError("Baserow table_id must be an int") from e

    return base_url, token, table_id


def _baserow_headers(token: str) -> dict[str, str]:
    t = (token or "").strip()
    if not t:
        raise ValueError("Baserow token is empty")
    # Baserow supports database tokens (Authorization: Token <token>)
    # and user access tokens (Authorization: JWT <token>).
    prefix = "JWT" if t.count(".") == 2 else "Token"
    return {"Authorization": f"{prefix} {t}", "Content-Type": "application/json"}


def _get_field_id_by_name(base_url: str, token: str, table_id: int, field_name: str) -> int:
    url = f"{base_url}/api/database/fields/table/{table_id}/"
    resp = requests.get(url, headers=_baserow_headers(token), timeout=30)
    resp.raise_for_status()

    fields = resp.json()
    if not isinstance(fields, list):
        raise ValueError("Unexpected Baserow response for fields list")

    target = field_name.strip().lower()
    for field in fields:
        name = str(field.get("name") or "").strip().lower()
        if name == target:
            field_id = field.get("id")
            if isinstance(field_id, int):
                return field_id
            try:
                return int(field_id)
            except Exception as e:  # noqa: BLE001
                raise ValueError(f"Field id for {field_name} is not an int") from e

    raise ValueError(f"Field '{field_name}' not found in Baserow table {table_id}")


def _find_reference_row_id(base_url: str, token: str, table_id: int, url_canonical: str) -> int | None:
    url = f"{base_url}/api/database/rows/table/{table_id}/"
    headers = _baserow_headers(token)

    params = {"size": 1, "user_field_names": "true", "filter__url_raw__equal": url_canonical}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code == 400:
        url_raw_field_id = _get_field_id_by_name(base_url, token, table_id, "url_raw")
        params = {
            "size": 1,
            "user_field_names": "true",
            f"filter__field_{url_raw_field_id}__equal": url_canonical,
        }
        resp = requests.get(url, params=params, headers=headers, timeout=30)

    resp.raise_for_status()

    data = resp.json()
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        return None

    row_id = results[0].get("id")
    if isinstance(row_id, int):
        return row_id
    try:
        return int(row_id)
    except Exception:
        return None


def _create_reference_row(base_url: str, token: str, table_id: int, url_canonical: str, user_comment: str) -> int:
    url = f"{base_url}/api/database/rows/table/{table_id}/"
    params = {"user_field_names": "true"}
    payload = {
        "url_raw": url_canonical,
        "user_comment": (user_comment or ""),
        "tags": [],
    }

    resp = requests.post(
        url,
        params=params,
        json=payload,
        headers=_baserow_headers(token),
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()
    row_id = data.get("id") if isinstance(data, dict) else None
    if isinstance(row_id, int):
        return row_id
    if row_id is None:
        raise ValueError("Baserow create-row response does not contain 'id'")
    return int(row_id)


def main(
    url_raw: str,
    baserow: baserow = "$res:u/theatmacreator/refbot_baserow",
    user_comment: str = "",
) -> dict:
    """
    Windmill transformation: create a reference row in Baserow with URL de-duplication.

    Returns:
      { reference_id:number; dedup:boolean; url_canonical:string }
    """

    url_canonical = _canonicalize_url(url_raw)

    base_url, token, table_id = _coerce_baserow_settings(baserow)
    existing_id = _find_reference_row_id(base_url, token, table_id, url_canonical)
    if existing_id is not None:
        return {
            "reference_id": existing_id,
            "dedup": True,
            "url_canonical": url_canonical,
        }

    reference_id = _create_reference_row(base_url, token, table_id, url_canonical, user_comment)
    return {
        "reference_id": reference_id,
        "dedup": False,
        "url_canonical": url_canonical,
    }
