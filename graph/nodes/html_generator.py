import asyncio
from pipeline.icon_fetcher import fetch_icons
from pipeline.image_fetcher import fetch_images
from pipeline.html_renderer import render_all_slides
from graph.state import PPTState


async def node_html_generator(state: PPTState) -> dict:
    slides_data = dict(state["slides_data"])

    # design_selector의 테마를 slides_data에 주입
    design_system = state.get("design_system", {})
    if design_system.get("theme"):
        slides_data["theme"] = design_system["theme"]

    icons = await fetch_icons(slides_data)
    images = await fetch_images(
        slides_data,
        pexels_key=state.get("pexels_key", ""),
        openai_key=state.get("openai_key", ""),
    )

    html_slides = await asyncio.to_thread(render_all_slides, slides_data, icons, images)
    return {"html_slides": html_slides}
