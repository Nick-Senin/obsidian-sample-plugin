from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit, urlunsplit
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Any, NotRequired, TypedDict

import requests
import wmill

from f.shared.llm_utils import create_llm_client, generate_completion, get_resource_compat


class baserow_config(TypedDict):
    """
    Expected keys for the BaserowConfig resource.

    Notes:
    - `references_table_id` is the table that stores references (must have fields: url_raw, user_comment, tags).
    - `tags_table_id` is the table that stores tags (must have fields: name, Active, description).
    """

    token: NotRequired[str]
    api_token: NotRequired[str]
    api_key: NotRequired[str]
    base_url: NotRequired[str]
    url: NotRequired[str]
    references_table_id: NotRequired[int]
    table_id: NotRequired[int]
    tags_table_id: NotRequired[int]
    tag_table_id: NotRequired[int]
    tags_table: NotRequired[int | str]


OPENROUTER_RESOURCE_PATH = os.environ.get("REFBOT_OPENROUTER_RESOURCE") or "u/theatmacreator/finer_c_openrouter"
OPENROUTER_MODEL = os.environ.get("REFBOT_OPENROUTER_MODEL") or "z-ai/glm-4.7-flash"
REFERENCES_TABLE_NAME = os.environ.get("REFBOT_REFERENCES_TABLE_NAME") or "References"
TAGS_TABLE_NAME = os.environ.get("REFBOT_TAGS_TABLE_NAME") or "Tags"


def _load_resource_compat(path: str) -> Any:
    try:
        return wmill.get_resource(path)
    except Exception as e:  # noqa: BLE001
        if "get_value_interpolated" not in str(e):
            raise

    base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
    workspace = os.environ.get("WM_WORKSPACE")
    token = os.environ.get("WM_TOKEN")
    if not base_url or not workspace or not token:
        raise

    encoded_path = quote(path, safe="/")
    url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def _baserow_api_base(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("Baserow base_url is empty")
    return base if base.endswith("/api") else f"{base}/api"


def _normalize_baserow_base_url(base_url: str) -> str:
    value = (base_url or "").strip().rstrip("/")
    if not value:
        return ""

    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        parsed = urlsplit(f"https://{value.lstrip('/')}")

    netloc = parsed.netloc.lower()
    if netloc in {"baserow.io", "www.baserow.io"}:
        parsed = parsed._replace(netloc="api.baserow.io")

    normalized = urlunsplit(
        (parsed.scheme or "https", parsed.netloc, parsed.path, parsed.query, parsed.fragment)
    ).rstrip("/")
    if normalized.endswith("/api"):
        normalized = normalized[: -len("/api")]
    return normalized


def _resolve_table_id_by_name(base_url: str, token: str, table_name: str) -> int:
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
            tables_raw = resp.json()
            if isinstance(tables_raw, dict) and isinstance(tables_raw.get("results"), list):
                tables = tables_raw["results"]
            else:
                tables = tables_raw
            if not isinstance(tables, list):
                continue

            for table in tables:
                t_id = table.get("id")
                t_name = str(table.get("name") or "")
                if isinstance(t_id, int) and t_name.strip().lower() == wanted:
                    matches.append((workspace_id, workspace_name, app_id, app_name, t_id, t_name))

    if not matches:
        raise ValueError(f"Baserow table '{table_name}' not found")

    if len(matches) == 1:
        return matches[0][4]

    # Prefer apps/groups that mention refbot.
    def score(m: tuple[int, str, int, str, int, str]) -> int:
        _, g_name, _, a_name, _, _ = m
        s = 0
        if "refbot" in (g_name or "").lower():
            s += 2
        if "refbot" in (a_name or "").lower():
            s += 3
        return s

    matches_sorted = sorted(matches, key=score, reverse=True)
    top = matches_sorted[0]
    if score(top) == score(matches_sorted[1]):
        details = ", ".join([f"{m[5]} (app={m[3]}, group={m[1]})" for m in matches_sorted[:5]])
        raise ValueError(f"Multiple Baserow tables named '{table_name}' found: {details}")
    return top[4]


def _coerce_baserow_settings(
    baserow: Any,
    tags_table_id_override: int | None = None,
) -> tuple[str, str, int, int]:
    if isinstance(baserow, str):
        value = baserow.strip()
        if not value:
            raise ValueError("BaserowConfig resource is an empty string")
        if value.startswith("$res:"):
            baserow = _load_resource_compat(value[len("$res:") :])
        elif value.startswith("u/") or value.startswith("f/"):
            baserow = _load_resource_compat(value)
        else:
            raise ValueError(
                "BaserowConfig must include base_url and table ids (got a token string only)"
            )

    if not isinstance(baserow, dict):
        raise ValueError("BaserowConfig must be a resource (string or object)")

    token = str(
        (baserow.get("token") or baserow.get("api_token") or baserow.get("api_key") or "")
    ).strip()
    if token.startswith("$var:"):
        token = str(wmill.get_variable(token[len("$var:") :]) or "").strip()
    base_url = _normalize_baserow_base_url(str((baserow.get("base_url") or baserow.get("url") or "")))

    references_table_id_raw = baserow.get("references_table_id") or baserow.get("table_id")
    tags_table_id_raw = (
        baserow.get("tags_table_id")
        or baserow.get("tag_table_id")
        or baserow.get("tags_table")
    )

    if not token:
        raise ValueError("BaserowConfig.token is missing")
    if not base_url:
        raise ValueError("BaserowConfig.base_url is missing")
    if references_table_id_raw is None:
        references_table_id = _resolve_table_id_by_name(base_url, token, REFERENCES_TABLE_NAME)
    else:
        try:
            references_table_id = int(references_table_id_raw)
        except Exception as e:  # noqa: BLE001
            raise ValueError("BaserowConfig.references_table_id (or table_id) must be an int") from e

    if tags_table_id_override is not None:
        tags_table_id = int(tags_table_id_override)
    elif tags_table_id_raw is None:
        tags_table_id = _resolve_table_id_by_name(base_url, token, TAGS_TABLE_NAME)
    else:
        try:
            tags_table_id = int(tags_table_id_raw)
        except Exception as e:  # noqa: BLE001
            raise ValueError("BaserowConfig.tags_table_id (or tag_table_id/tags_table) must be an int") from e

    return base_url, token, references_table_id, tags_table_id


def _baserow_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


def _baserow_get_row(base_url: str, token: str, table_id: int, row_id: int) -> dict:
    url = f"{base_url}/api/database/rows/table/{table_id}/{row_id}/"
    resp = requests.get(url, params={"user_field_names": "true"}, headers=_baserow_headers(token), timeout=30)
    if resp.status_code == 404:
        # Some Baserow setups expose list endpoints but not direct row-by-id reads.
        rows = _baserow_list_rows(base_url, token, table_id, page_size=200)
        for row in rows:
            try:
                if int(row.get("id")) == row_id:
                    return row
            except Exception:
                continue
        raise ValueError(f"Baserow row not found: table_id={table_id}, row_id={row_id}")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected Baserow response for get-row")
    return data


def _baserow_patch_row(base_url: str, token: str, table_id: int, row_id: int, payload: dict) -> dict:
    url = f"{base_url}/api/database/rows/table/{table_id}/{row_id}/"
    resp = requests.patch(
        url,
        params={"user_field_names": "true"},
        json=payload,
        headers=_baserow_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected Baserow response for patch-row")
    return data


def _baserow_list_rows(base_url: str, token: str, table_id: int, page_size: int = 200) -> list[dict]:
    url = f"{base_url}/api/database/rows/table/{table_id}/"
    headers = _baserow_headers(token)
    params = {"user_field_names": "true", "size": page_size}

    out: list[dict] = []
    next_url: str | None = None
    while True:
        if next_url:
            resp = requests.get(next_url, headers=headers, timeout=30)
        else:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected Baserow response for list-rows")
        results = data.get("results")
        if not isinstance(results, list):
            raise ValueError("Unexpected Baserow response for list-rows (missing results)")
        for row in results:
            if isinstance(row, dict):
                out.append(row)

        next_url_raw = data.get("next")
        next_url = str(next_url_raw).strip() if next_url_raw else None
        if not next_url:
            break

        if len(out) > 50_000:
            raise ValueError("Too many rows while listing Baserow table (safety limit)")

    return out


def _baserow_get_table_field_name_map(base_url: str, token: str, table_id: int) -> dict[str, str]:
    url = f"{base_url}/api/database/fields/table/{table_id}/"
    resp = requests.get(url, headers=_baserow_headers(token), timeout=30)
    resp.raise_for_status()
    fields = resp.json()
    if not isinstance(fields, list):
        raise ValueError("Unexpected Baserow response for fields list")

    out: dict[str, str] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if name:
            out[name.lower()] = name
    return out


def _extract_link_row_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[int] = []
        for item in value:
            if isinstance(item, int):
                out.append(item)
                continue
            if isinstance(item, str):
                try:
                    out.append(int(item))
                except Exception:
                    continue
                continue
            if isinstance(item, dict) and "id" in item:
                try:
                    out.append(int(item["id"]))
                except Exception:
                    continue
        return out
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        try:
            return [int(value)]
        except Exception:
            return []
    return []


def _norm_tag(value: str) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"\s+", " ", v)
    return v


def _parse_tags_from_llm(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []

    def _try_json(s: str) -> list[str] | None:
        try:
            obj = json.loads(s)
        except Exception:
            return None
        if not isinstance(obj, list):
            return None
        out: list[str] = []
        for item in obj:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out

    parsed = _try_json(raw)
    if parsed is None:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            parsed = _try_json(raw[start : end + 1])

    if parsed is not None:
        return parsed

    items: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        s = s.lstrip("-•*").strip()
        if not s:
            continue
        items.append(s)

    if len(items) <= 1:
        items = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return items


def _append_summary_to_comment(user_comment: str, summary: str) -> str:
    base = (user_comment or "").rstrip()
    block = f"AI tags summary (A8): {summary}".strip()
    if not base:
        return block
    if "AI tags summary (A8):" in base:
        return base
    return f"{base}\n\n---\n{block}"


def _extract_explicit_candidates(user_comment: str, max_tags: int) -> list[str]:
    if max_tags <= 0:
        return []

    text = (user_comment or "").strip()
    if not text:
        return []

    lower_text = text.lower()
    if lower_text.startswith(("tags:", "tag:", "теги:", "тег:")):
        after = text.split(":", 1)[1].strip() if ":" in text else ""
        parts = [p.strip() for p in after.replace(";", ",").split(",") if p.strip()]
        return parts[:max_tags]

    # If the whole comment is short, treat it as a tag candidate.
    if len(text) <= 80 and "\n" not in text and "http://" not in text and "https://" not in text:
        if len(text.split()) <= 6:
            return [text]

    candidates: list[str] = []

    # Lines like: "tags: a, b" / "теги: a, b"
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        lower = s.lower()
        if lower.startswith("tags:") or lower.startswith("tag:") or lower.startswith("теги:") or lower.startswith("тег:"):
            after = s.split(":", 1)[1].strip()
            if after:
                candidates.extend([p.strip() for p in after.replace(";", ",").split(",") if p.strip()])

    # Hashtags inside the comment.
    for m in re.finditer(r"(?:^|[\s])#([^\s#]{2,64})", text):
        candidates.append(m.group(1).replace("_", " ").strip())

    # Quoted short phrases.
    for m in re.finditer(r"[«\"]([^»\"]{2,64})[»\"]", text):
        phrase = m.group(1).strip()
        if phrase:
            candidates.append(phrase)

    # Normalize + unique + cap
    uniq: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        raw = (c or "").strip()
        if not raw:
            continue
        norm = _norm_tag(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        uniq.append(raw)
        if len(uniq) >= max_tags:
            break
    return uniq


def _generate_tag_candidates(
    url_raw: str,
    user_comment: str,
    max_tags: int,
    model: str,
) -> tuple[list[str], str]:
    if max_tags <= 0:
        return [], "candidates=[]"

    resource = get_resource_compat(OPENROUTER_RESOURCE_PATH)
    client = create_llm_client(resource)

    prompt = f"""# Роль
Ты помощник, который подбирает теги для заметки/ссылки.

# Вход
- url_raw: {url_raw}
- user_comment: {user_comment}

# Задача
Предложи до {max_tags} тегов. Теги — короткие фразы на русском языке (1–4 слова), без символа #, без кавычек.
Если в комментарии явно есть готовый тег/формулировка — используй её дословно.

# Формат ответа (строго)
Верни ТОЛЬКО JSON-массив строк, например:
["тег один", "тег два"]
"""

    completion = generate_completion(
        client=client,
        prompt=prompt,
        model=model,
        temperature=0.2,
        max_tokens=200,
    )

    candidates_raw = _parse_tags_from_llm(completion)
    uniq: list[str] = []
    seen: set[str] = set()
    for t in candidates_raw:
        norm = _norm_tag(t)
        if not norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        uniq.append(t.strip())
        if len(uniq) >= max_tags:
            break

    summary = f"candidates={uniq}"
    return uniq, summary


def _build_existing_tags_index(tags_rows: list[dict], name_key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in tags_rows:
        if not isinstance(row, dict):
            continue
        row_id = row.get("id")
        try:
            tag_id = int(row_id)
        except Exception:
            continue

        name_value = row.get(name_key)
        if not isinstance(name_value, str):
            continue
        norm = _norm_tag(name_value)
        if not norm:
            continue
        out[norm] = tag_id
    return out


def _baserow_create_tag(
    base_url: str,
    token: str,
    tags_table_id: int,
    field_name_map: dict[str, str],
    raw_name: str,
) -> int:
    name_field = field_name_map.get("name") or "name"
    active_field = field_name_map.get("active") or field_name_map.get("активный")
    description_field = field_name_map.get("description") or field_name_map.get("описание")

    payload: dict[str, Any] = {name_field: raw_name}
    if active_field:
        payload[active_field] = True
    if description_field:
        payload[description_field] = ""

    url = f"{base_url}/api/database/rows/table/{tags_table_id}/"
    resp = requests.post(
        url,
        params={"user_field_names": "true"},
        json=payload,
        headers=_baserow_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or "id" not in data:
        raise ValueError("Unexpected Baserow response for create-tag")
    return int(data["id"])


def main(
    reference_id: float,
    baserow: baserow_config | str = "$res:u/theatmacreator/refbot_baserow",
    tags_table_id: int | None = None,
    llm_model: str = "z-ai/glm-4.7-flash",
    max_tags: int = 6,
    max_new_tags: int = 2,
) -> dict:
    """
    Windmill transformation: AI tag autocreate (2 tables: references + tags).

    Inputs:
    - baserow: BaserowConfig resource (object) with base_url, token, references_table_id, tags_table_id
    - reference_id: number
    - llm_model: OpenRouter model slug (default from REFBOT_OPENROUTER_MODEL or openai/chatgpt-4o-latest)
    - max_tags: number (default 6)
    - max_new_tags: number (default 2)

    Output:
      { ok:true; created_tag_ids:number[]; applied_tag_ids:number[]; summary:string }

    Optional behavior:
    - If env `REFBOT_APPEND_SUMMARY=1`, appends a short summary to `user_comment`.
    """

    try:
        reference_row_id = int(reference_id)
    except Exception as e:  # noqa: BLE001
        raise ValueError("reference_id must be a number") from e

    max_tags = max(0, int(max_tags))
    max_new_tags = max(0, int(max_new_tags))
    model_slug = (llm_model or OPENROUTER_MODEL).strip() or OPENROUTER_MODEL

    base_url, token, references_table_id, tags_table_id = _coerce_baserow_settings(
        baserow,
        tags_table_id_override=tags_table_id,
    )

    reference = _baserow_get_row(base_url, token, references_table_id, reference_row_id)
    url_raw = str(reference.get("url_raw") or "").strip()
    user_comment = str(reference.get("user_comment") or "")
    old_tag_ids = _extract_link_row_ids(reference.get("tags"))

    tags_field_map = _baserow_get_table_field_name_map(base_url, token, tags_table_id)
    tags_name_field = tags_field_map.get("name") or "name"
    tags_rows = _baserow_list_rows(base_url, token, tags_table_id, page_size=200)
    existing_by_norm = _build_existing_tags_index(tags_rows, tags_name_field)

    explicit = _extract_explicit_candidates(user_comment, max_tags=max_tags)
    remaining = max(0, max_tags - len(explicit))
    llm_candidates: list[str] = []
    llm_summary = "candidates=[]"
    if remaining > 0:
        try:
            llm_candidates, llm_summary = _generate_tag_candidates(
                url_raw=url_raw,
                user_comment=user_comment,
                max_tags=remaining,
                model=model_slug,
            )
        except Exception as e:  # noqa: BLE001
            llm_candidates = []
            llm_summary = f"llm_error={str(e)}"

    candidates: list[str] = []
    seen_norm: set[str] = set()
    for raw in explicit + llm_candidates:
        s = (raw or "").strip()
        if not s:
            continue
        norm = _norm_tag(s)
        if not norm or norm in seen_norm:
            continue
        seen_norm.add(norm)
        candidates.append(s)

    created_tag_ids: list[int] = []
    selected_tag_ids: list[int] = []
    created_new = 0

    for raw in candidates:
        raw_clean = (raw or "").strip()
        norm = _norm_tag(raw_clean)
        if not norm:
            continue

        existing_id = existing_by_norm.get(norm)
        if existing_id is not None:
            selected_tag_ids.append(existing_id)
            continue

        if created_new >= max_new_tags:
            continue

        new_id = _baserow_create_tag(
            base_url=base_url,
            token=token,
            tags_table_id=tags_table_id,
            field_name_map=tags_field_map,
            raw_name=raw_clean,
        )
        created_new += 1
        created_tag_ids.append(new_id)
        selected_tag_ids.append(new_id)
        existing_by_norm[norm] = new_id

    final_tag_ids: list[int] = []
    seen_ids: set[int] = set()
    for tag_id in old_tag_ids + selected_tag_ids:
        if tag_id in seen_ids:
            continue
        seen_ids.add(tag_id)
        final_tag_ids.append(tag_id)

    summary = "; ".join(
        [
            llm_summary,
            f"created_tag_ids={created_tag_ids}",
            f"selected_tag_ids={selected_tag_ids}",
            f"old_tag_ids={old_tag_ids}",
            f"final_tag_ids={final_tag_ids}",
        ]
    )

    patch_payload: dict[str, Any] = {"tags": final_tag_ids}
    if (os.environ.get("REFBOT_APPEND_SUMMARY") or "").strip() == "1":
        patch_payload["user_comment"] = _append_summary_to_comment(user_comment, summary)

    _baserow_patch_row(base_url, token, references_table_id, reference_row_id, patch_payload)

    return {
        "ok": True,
        "created_tag_ids": created_tag_ids,
        "applied_tag_ids": final_tag_ids,
        "summary": summary,
    }
