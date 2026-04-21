from typing import TypedDict


class PPTState(TypedDict):
    # ── 런타임 설정 (호출 시 전달) ──
    folder: str
    model: str          # "claude" | "gemini"
    api_key: str
    openai_key: str
    pexels_key: str
    goal: str
    audience_hint: str
    theme_hint: str
    output_dir: str

    # ── 파이프라인 상태 ──
    md_content: str
    direction: dict      # audience, tone, brand, slide_count, language, core_message, ...
    design_system: dict  # brand + preset info
    marp_md: str         # Marp 포맷 마크다운 (outline_planner 출력)
    slides_data: dict    # 슬라이드 메타 (title, brand)
    html_slides: list    # v1 하위호환용
    validation_issues: list
    iteration_count: int
    output_path: str
