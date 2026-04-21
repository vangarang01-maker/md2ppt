from graph.state import PPTState


_PRESETS = {
    "starbucks": {
        "bg": "#00382B", "surface": "#1E3932", "accent": "#00A862",
        "text": "#FFFFFF", "subtext": "#86C8A8", "body": "#C8E6D5",
    },
    "dark_tech": {
        "bg": "#0D1117", "surface": "#161B22", "accent": "#58A6FF",
        "text": "#FFFFFF", "subtext": "#8B949E", "body": "#C9D1D9",
    },
    "minimal": {
        "bg": "#FFFFFF", "surface": "#F8F9FA", "accent": "#2563EB",
        "text": "#1F2937", "subtext": "#6B7280", "body": "#374151",
    },
    "corporate": {
        "bg": "#003366", "surface": "#004080", "accent": "#FFB800",
        "text": "#FFFFFF", "subtext": "#AABBCC", "body": "#CCE0FF",
    },
    "default": {
        "bg": "#1A1A2E", "surface": "#16213E", "accent": "#4D9DFF",
        "text": "#FFFFFF", "subtext": "#AABBCC", "body": "#DDEEFF",
    },
}

_PRESET_NAMES = {
    "starbucks": "스타벅스 그린",
    "dark_tech": "다크 테크",
    "minimal": "미니멀 화이트",
    "corporate": "코퍼레이트 블루",
    "default": "다크 네이비",
}


async def node_design_selector(state: PPTState) -> dict:
    direction = state.get("direction", {})
    brand = direction.get("brand", "default")
    theme = _PRESETS.get(brand, _PRESETS["default"])

    design_system = {
        "theme": theme,
        "brand": brand,
        "preset_name": _PRESET_NAMES.get(brand, "다크 네이비"),
    }
    return {"design_system": design_system}
