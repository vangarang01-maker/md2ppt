import asyncio
import base64

import httpx

_PEXELS_BASE = "https://api.pexels.com/v1/search"
_IMAGE_SLIDE_TYPES = {"title", "section", "quote", "bento"}

_DALLE_STYLE = (
    "Cinematic, ultra-high quality, dramatic professional lighting, dark premium atmosphere, "
    "no text, no letters, no watermarks, photorealistic."
)

_DALLE_PROMPTS = {
    "title": (
        "Wide-angle cinematic background for a business presentation about {title}. "
        "Dark moody atmosphere, subtle geometric abstract shapes, premium corporate aesthetic. " + _DALLE_STYLE
    ),
    "section": (
        "Abstract conceptual visualization for the topic '{title}'. "
        "Dark background, glowing accent elements, modern minimal design. " + _DALLE_STYLE
    ),
    "quote": (
        "Minimalist dark abstract background with soft light bokeh and elegant textures. "
        "Evokes depth and contemplation. " + _DALLE_STYLE
    ),
}


async def fetch_images(
    slides_data: dict,
    pexels_key: str = "",
    openai_key: str = "",
) -> dict[int, str]:
    """Returns {slide_index: base64_data_uri} for slides that use background images."""
    if not openai_key and not pexels_key:
        return {}

    slides = slides_data.get("slides", [])
    tasks = []
    indices = []

    for i, slide in enumerate(slides):
        if slide.get("type") in _IMAGE_SLIDE_TYPES:
            tasks.append(_fetch_with_fallback(slide, openai_key, pexels_key))
            indices.append(i)

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = {}
    dalle_unavailable = False
    for idx, result in zip(indices, results):
        if isinstance(result, DalleUnavailable):
            dalle_unavailable = True
        elif isinstance(result, str) and result:
            images[idx] = result

    # DALL-E 크레딧 부족 시 전체를 Pexels로 재시도
    if dalle_unavailable and pexels_key:
        retry_tasks = []
        retry_indices = []
        for i, slide in enumerate(slides):
            if slide.get("type") in _IMAGE_SLIDE_TYPES and i not in images:
                retry_tasks.append(_pexels(slide, pexels_key))
                retry_indices.append(i)
        if retry_tasks:
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
            for idx, result in zip(retry_indices, retry_results):
                if isinstance(result, str) and result:
                    images[idx] = result

    return images


class DalleUnavailable(Exception):
    """DALL-E를 사용할 수 없을 때 Pexels 폴백을 알리는 sentinel."""


async def _fetch_with_fallback(slide: dict, openai_key: str, pexels_key: str) -> str:
    if openai_key:
        try:
            return await _dalle(slide, openai_key)
        except Exception as e:
            msg = str(e).lower()
            if "billing" in msg or "quota" in msg or "rate" in msg or "limit" in msg:
                raise DalleUnavailable(
                    "OpenAI 크레딧 부족 — Pexels로 폴백합니다."
                ) from e
            # 그 외 에러도 Pexels로 폴백
    if pexels_key:
        try:
            return await _pexels(slide, pexels_key)
        except Exception:
            return ""
    return ""


async def _dalle(slide: dict, api_key: str) -> str:
    from openai import AsyncOpenAI, BadRequestError, AuthenticationError
    slide_type = slide.get("type", "title")
    title = slide.get("title", "")
    prompt_template = _DALLE_PROMPTS.get(slide_type, _DALLE_PROMPTS["title"])
    prompt = prompt_template.format(title=title)

    client = AsyncOpenAI(api_key=api_key)
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        response_format="b64_json",
        n=1,
    )
    b64 = response.data[0].b64_json
    return f"data:image/png;base64,{b64}"


async def _pexels(slide: dict, api_key: str) -> str:
    title = slide.get("title", "")
    words = [w for w in title.split() if len(w) > 1][:4]
    query = " ".join(words) or "technology abstract"
    if slide.get("type") == "quote":
        query = "abstract minimal dark texture"

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            _PEXELS_BASE,
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "landscape", "per_page": 1},
        )
        if r.status_code != 200:
            return ""
        photos = r.json().get("photos", [])
        if not photos:
            return ""
        img_url = photos[0].get("src", {}).get("large2x", "")
        if not img_url:
            return ""
        img_r = await client.get(img_url, timeout=15.0)
        if img_r.status_code != 200:
            return ""
        b64 = base64.b64encode(img_r.content).decode()
        return f"data:image/jpeg;base64,{b64}"
