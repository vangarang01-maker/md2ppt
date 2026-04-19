import re

import httpx

_ICONIFY_BASE = "https://api.iconify.design"
_TIMEOUT = 5.0


def _normalize_svg(svg: str) -> str:
    """SVG의 고정 width/height(e.g. '1em', '24px')를 100%로 교체해 컨테이너 크기를 따르게 함."""
    svg = re.sub(r'(<svg[^>]*)\swidth="[^"]*"', r'\1 width="100%"', svg)
    svg = re.sub(r'(<svg[^>]*)\sheight="[^"]*"', r'\1 height="100%"', svg)
    return svg


def _collect_icon_names(slides_data: dict) -> set[str]:
    names = set()
    for slide in slides_data.get("slides", []):
        if slide.get("icon"):
            names.add(slide["icon"])
        for stat in slide.get("stats", []):
            if stat.get("icon"):
                names.add(stat["icon"])
    return names


async def fetch_icons(slides_data: dict) -> dict[str, str]:
    """Iconify API에서 SVG를 가져와 {icon_name: svg_string} 반환."""
    names = _collect_icon_names(slides_data)
    if not names:
        return {}

    icons: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for name in names:
            parts = name.split(":", 1)
            if len(parts) != 2:
                continue
            prefix, icon = parts
            try:
                r = await client.get(f"{_ICONIFY_BASE}/{prefix}/{icon}.svg")
                if r.status_code == 200:
                    icons[name] = _normalize_svg(r.text)
            except Exception:
                pass  # 아이콘 로드 실패 시 해당 아이콘만 건너뜀

    return icons
