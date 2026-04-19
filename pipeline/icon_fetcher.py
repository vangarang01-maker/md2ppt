import httpx

_ICONIFY_BASE = "https://api.iconify.design"
_TIMEOUT = 5.0


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
                    icons[name] = r.text
            except Exception:
                pass  # 아이콘 로드 실패 시 해당 아이콘만 건너뜀

    return icons
