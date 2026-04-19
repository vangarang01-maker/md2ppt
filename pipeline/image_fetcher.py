import asyncio
import base64

import httpx

_UNSPLASH_BASE = "https://api.unsplash.com/photos/random"
_IMAGE_SLIDE_TYPES = {"title", "section", "quote"}


async def fetch_images(slides_data: dict, api_key: str) -> dict[int, str]:
    """Returns {slide_index: base64_data_uri} for slides that use background images."""
    if not api_key:
        return {}

    slides = slides_data.get("slides", [])
    tasks = []
    indices = []

    for i, slide in enumerate(slides):
        if slide.get("type") in _IMAGE_SLIDE_TYPES:
            query = _build_query(slide)
            tasks.append(_fetch_one(query, api_key))
            indices.append(i)

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = {}
    for idx, result in zip(indices, results):
        if isinstance(result, str) and result:
            images[idx] = result
    return images


def _build_query(slide: dict) -> str:
    title = slide.get("title", "")
    words = [w for w in title.split() if len(w) > 1][:4]
    query = " ".join(words)
    slide_type = slide.get("type", "")
    if slide_type == "quote":
        return f"{query} abstract minimal" if query else "abstract minimal dark"
    return query or "technology abstract"


async def _fetch_one(query: str, api_key: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                _UNSPLASH_BASE,
                params={"query": query, "orientation": "landscape", "client_id": api_key},
            )
            if r.status_code != 200:
                return ""
            img_url = r.json().get("urls", {}).get("small", "")
            if not img_url:
                return ""
            img_r = await client.get(img_url, timeout=10.0)
            if img_r.status_code != 200:
                return ""
            b64 = base64.b64encode(img_r.content).decode()
            return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return ""
