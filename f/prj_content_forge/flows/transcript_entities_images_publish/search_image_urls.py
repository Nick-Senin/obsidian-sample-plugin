from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


def _query(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    headers = {"User-Agent": "windmill-flow/transcript-entities-images"}
    try:
        full_url = f"{url}?{urlencode(params)}"
        req = Request(full_url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _image_infos_from_pages(pages: Any) -> list[dict[str, Any]]:
    if isinstance(pages, dict):
        page_values = list(pages.values())
    elif isinstance(pages, list):
        page_values = pages
    else:
        page_values = []

    infos: list[dict[str, Any]] = []
    for page in page_values:
        if not isinstance(page, dict):
            continue
        for info in page.get("imageinfo", []) or []:
            if isinstance(info, dict) and isinstance(info.get("url"), str):
                infos.append(info)
    return infos


def _pick_infos(
    infos: list[dict[str, Any]],
    *,
    images_per_entity: int,
    min_width: int,
    min_height: int,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for info in infos:
        url = info.get("url")
        if not isinstance(url, str) or not url or url in seen:
            continue
        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)
        if width < min_width or height < min_height:
            continue
        seen.add(url)
        picked.append(
            {
                "url": url,
                "width": width,
                "height": height,
                "mime": info.get("mime"),
                "size": info.get("size"),
            }
        )
        if len(picked) >= images_per_entity:
            break
    return picked


def _wikidata_image_infos(entity: str) -> list[dict[str, Any]]:
    search = _query(
        WIKIDATA_API_URL,
        {
            "action": "wbsearchentities",
            "format": "json",
            "search": entity,
            "language": "en",
        },
    )
    if not search or not search.get("search"):
        return []
    qid = search["search"][0].get("id")
    if not isinstance(qid, str) or not qid:
        return []
    ent = _query(
        WIKIDATA_API_URL,
        {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "claims",
        },
    )
    try:
        filename = ent["entities"][qid]["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
    except Exception:
        return []
    if not isinstance(filename, str) or not filename:
        return []
    commons = _query(
        COMMONS_API_URL,
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|mime|size",
            "titles": f"File:{filename}",
        },
    )
    pages = (commons or {}).get("query", {}).get("pages", []) or []
    return _image_infos_from_pages(pages)


def _commons_search_infos(entity: str) -> list[dict[str, Any]]:
    files = _query(
        COMMONS_API_URL,
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": entity,
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url|mime|size",
        },
    )
    pages = (files or {}).get("query", {}).get("pages", []) or []
    return _image_infos_from_pages(pages)


def main(
    entities: list[str],
    images_per_entity: int = 1,
    min_width: int = 100,
    min_height: int = 100,
    use_wikidata: bool = True,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for entity in entities or []:
        entity = str(entity).strip()
        if not entity:
            continue
        infos = _wikidata_image_infos(entity) if use_wikidata else []
        if not infos:
            infos = _commons_search_infos(entity)
        images = _pick_infos(
            infos,
            images_per_entity=max(1, int(images_per_entity or 1)),
            min_width=max(0, int(min_width or 0)),
            min_height=max(0, int(min_height or 0)),
        )
        if images:
            results.append({"entity": entity, "images": images})
    return {"results": results}
