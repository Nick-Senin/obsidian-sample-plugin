from __future__ import annotations

import re
from typing import Any

import requests


try:
    import wmill  # type: ignore
except Exception:  # pragma: no cover
    class _WmillStub:
        def write_s3_file(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available outside Windmill runtime")

        def get_presigned_s3_public_url(self, *_args, **_kwargs):
            raise RuntimeError("wmill is not available outside Windmill runtime")

    wmill = _WmillStub()  # type: ignore


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


def _pick_image_urls(
    pages: list[dict[str, Any]],
    *,
    images_per_entity: int,
    min_width: int,
    min_height: int,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page in pages:
        for info in page.get("imageinfo", []) or []:
            url = info.get("url")
            if not isinstance(url, str) or not url:
                continue
            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            if width < min_width or height < min_height:
                continue
            if url in seen:
                continue
            seen.add(url)
            picked.append(info)
            if len(picked) >= images_per_entity:
                return picked

    return picked


def _slug(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-zА-Яа-я_.-]+", "_", s)
    return s.strip("_") or "entity"


def _commons_query(params: dict[str, Any]) -> dict[str, Any] | None:
    headers = {"User-Agent": "windmill-script/commons-images"}
    try:
        resp = requests.get(COMMONS_API_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError:
        return None


def _wikidata_query(params: dict[str, Any]) -> dict[str, Any] | None:
    headers = {"User-Agent": "windmill-script/commons-images"}
    try:
        resp = requests.get(WIKIDATA_API_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError:
        return None


def _download(url: str, *, max_bytes: int) -> bytes | None:
    headers = {"User-Agent": "windmill-script/commons-images"}
    try:
        with requests.get(url, headers=headers, timeout=60, stream=True) as resp:
            resp.raise_for_status()
            content = b"".join(resp.iter_content(chunk_size=1024 * 64))
            if len(content) > max_bytes:
                return None
            return content
    except requests.HTTPError:
        return None


def main(
    entities: list[str],
    images_per_entity: int = 1,
    min_width: int = 100,
    min_height: int = 100,
    s3_prefix: str = "commons_images",
    max_file_size_mb: int = 10,
    use_wikidata: bool = True,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    max_bytes = max(0, int(max_file_size_mb)) * 1024 * 1024

    for entity in entities:
        pages: list[dict[str, Any]] = []

        if use_wikidata:
            search = _wikidata_query(
                {
                    "action": "wbsearchentities",
                    "format": "json",
                    "search": entity,
                    "language": "en",
                }
            )
            if search and search.get("search"):
                qid = search["search"][0].get("id")
                if isinstance(qid, str) and qid:
                    ent = _wikidata_query(
                        {
                            "action": "wbgetentities",
                            "format": "json",
                            "ids": qid,
                            "props": "claims",
                        }
                    )
                    try:
                        filename = (
                            ent["entities"][qid]["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
                        )
                    except Exception:  # noqa: BLE001
                        filename = None

                    if isinstance(filename, str) and filename:
                        commons = _commons_query(
                            {
                                "action": "query",
                                "format": "json",
                                "prop": "imageinfo",
                                "iiprop": "url|mime|size",
                                "titles": f"File:{filename}",
                            }
                        )
                        if commons:
                            pages = commons.get("query", {}).get("pages", []) or []

        if not pages:
            # Commons category search
            category = _commons_query(
                {
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": f"Category:{entity}",
                }
            )
            category_title = None
            if category:
                hits = category.get("query", {}).get("search", []) or []
                if hits:
                    category_title = hits[0].get("title")

            pageids: list[int] = []
            if isinstance(category_title, str) and category_title:
                members = _commons_query(
                    {
                        "action": "query",
                        "format": "json",
                        "list": "categorymembers",
                        "cmtitle": category_title,
                        "cmlimit": 50,
                    }
                )
                if members:
                    for m in members.get("query", {}).get("categorymembers", []) or []:
                        pid = m.get("pageid")
                        if isinstance(pid, int):
                            pageids.append(pid)

            if pageids:
                info = _commons_query(
                    {
                        "action": "query",
                        "format": "json",
                        "prop": "imageinfo",
                        "iiprop": "url|mime|size",
                        "pageids": "|".join(str(x) for x in pageids),
                    }
                )
                if info:
                    pages = info.get("query", {}).get("pages", []) or []
            else:
                # file search fallback
                files = _commons_query(
                    {
                        "action": "query",
                        "format": "json",
                        "generator": "search",
                        "gsrsearch": entity,
                        "gsrlimit": 10,
                    }
                )
                if files:
                    pages = files.get("query", {}).get("pages", []) or []

        # Pick more candidates than we strictly need, so we can skip downloads
        # that are too large or fail without dropping the whole entity.
        picked = _pick_image_urls(
            pages,
            images_per_entity=max(10, max(1, images_per_entity)),
            min_width=min_width,
            min_height=min_height,
        )
        if not picked:
            continue

        images: list[dict[str, Any]] = []
        for info in picked:
            if len(images) >= images_per_entity:
                break
            url = info.get("url")
            if not isinstance(url, str) or not url:
                continue
            content = _download(url, max_bytes=max_bytes)
            if content is None:
                continue

            s3obj = {"s3": f"/{s3_prefix}/{_slug(entity)}/{_slug(url.split('/')[-1])}"}
            saved = wmill.write_s3_file(s3obj, content)
            public_url = wmill.get_presigned_s3_public_url(saved)
            images.append({"s3": saved["s3"], "url": public_url})

        if images:
            results.append({"entity": entity, "images": images})

    return {"results": results}
