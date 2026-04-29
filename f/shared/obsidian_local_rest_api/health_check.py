from __future__ import annotations

from typing import Any, TypedDict

import requests
import wmill


class ObsidianLocalRestApiResource(TypedDict):
    baseUrl: str
    apiKey: str
    timeoutSeconds: int


def _normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        raise ValueError("baseUrl is required")
    return base_url.rstrip("/")


def _get_timeout_seconds(resource: ObsidianLocalRestApiResource, override: int | None) -> int:
    if override is not None:
        if not isinstance(override, int) or override <= 0:
            raise ValueError("timeout_seconds_override must be a positive int")
        return override
    t = resource.get("timeoutSeconds", 10)
    if not isinstance(t, int) or t <= 0:
        return 10
    return t


def main(
    obsidian_resource_path: str = "u/theatmacreator/obsidian_local_rest_api",
    timeout_seconds_override: int | None = None,
) -> dict[str, Any]:
    """
    HEALTH_CHECK_OBSIDIAN_LOCAL_REST_API - проверяет доступность obsidian-local-rest-api из Windmill.

    @param obsidian_resource_path Путь ресурса Windmill (u/...); должен содержать baseUrl/apiKey/timeoutSeconds
    @param timeout_seconds_override (опционально) Таймаут HTTP в секундах
    """
    resource = wmill.get_resource(obsidian_resource_path.strip())
    if not isinstance(resource, dict):
        raise ValueError("resource must be an object")

    obsidian: ObsidianLocalRestApiResource = resource  # type: ignore[assignment]

    base_url = _normalize_base_url(obsidian.get("baseUrl", ""))
    api_key = (obsidian.get("apiKey", "") or "").strip()
    if not api_key:
        raise ValueError("apiKey is required (use a secret variable reference in the resource)")

    timeout_s = _get_timeout_seconds(obsidian, timeout_seconds_override)

    verify_tls = True
    if base_url.startswith("https://"):
        # plugin uses a self-signed cert by default; keep it simple for server-local usage.
        verify_tls = False
        requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    session = requests.Session()

    unauth_url = f"{base_url}/"
    auth_url = f"{base_url}/commands/"

    unauth_resp = session.get(unauth_url, timeout=timeout_s, verify=verify_tls)
    unauth_body: dict[str, Any] | str
    try:
        unauth_body = unauth_resp.json()
    except Exception:
        unauth_body = (unauth_resp.text or "")[:500]

    auth_resp = session.get(
        auth_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout_s,
        verify=verify_tls,
    )
    auth_body: dict[str, Any] | str
    try:
        auth_body = auth_resp.json()
    except Exception:
        auth_body = (auth_resp.text or "")[:500]

    return {
        "ok": unauth_resp.ok and auth_resp.ok,
        "base_url": base_url,
        "timeout_seconds": timeout_s,
        "tls_verify": verify_tls,
        "unauth": {
            "url": unauth_url,
            "status": unauth_resp.status_code,
            "ok": unauth_resp.ok,
            "body": unauth_body,
        },
        "auth": {
            "url": auth_url,
            "status": auth_resp.status_code,
            "ok": auth_resp.ok,
            "body": auth_body,
        },
    }

