from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError


try:
    import wmill  # type: ignore
except Exception:  # pragma: no cover
    class _WmillStub:
        def get_resource(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available outside Windmill runtime")

    wmill = _WmillStub()  # type: ignore


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        # ```json\n...\n```
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    return s.strip()


def _dedup_entities(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        v = v.strip()
        if not v:
            continue
        key = v.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _parse_entities(raw: str) -> list[str]:
    """
    Accepts JSON (optionally inside ```json code fences) in one of the forms:
    - ["Alice", "Bob"]
    - {"entities": ["Alice", "Bob"]}
    - [{"name": "Alice"}, {"name": "Bob"}]
    """
    s = _strip_code_fence(raw)
    try:
        data = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc

    entities: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                entities.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                entities.append(item["name"])
    elif isinstance(data, dict):
        arr = data.get("entities")
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict) and isinstance(item.get("name"), str):
                    entities.append(item["name"])
    else:
        raise ValueError("JSON must be an array or object")

    return _dedup_entities(entities)


def main(text: str, entities_count: int = 10) -> dict[str, Any]:
    if entities_count <= 0:
        return {"entities": []}

    resource = get_resource("u/theatmacreator/finer_c_openrouter")
    client = create_llm_client(resource)
    raw = generate_completion(prompt=_entity_prompt(text, entities_count), client=client)
    entities = _parse_entities(raw)[:entities_count]
    return {"entities": entities, "raw": raw}


def _entity_prompt(text: str, entities_count: int) -> str:
    return (
        "Extract the most concrete named entities and useful visual search terms "
        f"from the transcript below. Return only JSON in this exact shape: "
        f'{{"entities":["entity 1","entity 2"]}}. '
        f"Return at most {entities_count} entities. Prefer people, products, "
        "organizations, places, technologies, and visually searchable concepts.\n\n"
        f"Transcript:\n{text}"
    )


def get_resource(path: str) -> Any:
    try:
        value = wmill.get_resource(path)
    except Exception:
        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/resources/get_value/{encoded_path}"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        value = json.loads(body) if body else {}
    return _resolve_secret_refs(value)


def _get_variable(path: str) -> str:
    try:
        return wmill.get_variable(path)  # type: ignore[attr-defined]
    except Exception:
        base_url = os.environ.get("BASE_INTERNAL_URL") or os.environ.get("BASE_URL")
        workspace = os.environ.get("WM_WORKSPACE")
        token = os.environ.get("WM_TOKEN")
        if not base_url or not workspace or not token:
            raise

        encoded_path = quote(path, safe="/")
        url = f"{base_url}/api/w/{workspace}/variables/get/{encoded_path}"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict) and "value" in payload:
            return payload["value"] or ""
        if isinstance(payload, str):
            return payload
        raise ValueError(f"Unexpected variable payload for {path}: {type(payload).__name__}")


def _resolve_secret_refs(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("$var:"):
        return _get_variable(value[len("$var:"):])
    if isinstance(value, dict):
        return {k: _resolve_secret_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_secret_refs(item) for item in value]
    return value


def create_llm_client(resource: Any) -> Any:
    return resource


def generate_completion(*, prompt: str, client: Any) -> str:
    if not isinstance(client, dict):
        raise ValueError("OpenRouter resource must be a dict")
    api_key = client.get("apiKey") or client.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("OpenRouter resource has no apiKey")

    payload = json.dumps(
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 350,
        }
    ).encode("utf-8")
    req = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hub.nicksenin.com",
            "X-Title": str(client.get("X_Title") or client.get("X-Title") or "Windmill"),
        },
        data=payload,
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP error {exc.code}: {body[:500]}") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ValueError(f"Unexpected OpenRouter response: {data}") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenRouter returned empty content")
    return content.strip()
