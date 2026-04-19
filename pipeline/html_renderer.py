from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "slides"

_DEFAULT_THEME = {
    "bg":      "#1A1A2E",
    "surface": "#16213E",
    "accent":  "#4D9DFF",
    "text":    "#FFFFFF",
    "subtext": "#AABBCC",
    "body":    "#DDEEFF",
}


def _normalize_theme(raw: dict) -> dict:
    merged = {**_DEFAULT_THEME}
    for k, v in raw.items():
        if v and k in merged:
            merged[k] = v if v.startswith("#") else f"#{v}"
    return merged


def render_all_slides(
    slides_data: dict,
    icons: dict[str, str] | None = None,
    images: dict[int, str] | None = None,
) -> list[str]:
    theme = _normalize_theme(slides_data.get("theme", {}))
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    icons = icons or {}
    images = images or {}

    html_slides = []
    for i, slide in enumerate(slides_data.get("slides", [])):
        slide_type = slide.get("type", "content")
        try:
            template = env.get_template(f"{slide_type}.html")
        except Exception:
            template = env.get_template("content.html")
        html_slides.append(
            template.render(slide=slide, theme=theme, index=i, icons=icons, image_url=images.get(i, ""))
        )

    return html_slides
