import re
from graph.state import PPTState


def _count_marp_slides(marp_md: str) -> int:
    # Remove YAML frontmatter (first ---...--- block)
    content = re.sub(r'^---\n.*?\n---\n?', '', marp_md.strip(), count=1, flags=re.DOTALL)
    # Each --- on its own line starts a new slide; content before first --- is slide 1
    parts = re.split(r'\n---\n', content)
    return len(parts)


async def node_layout_validator(state: PPTState) -> dict:
    marp_md = state.get("marp_md", "")
    issues: list[str] = []

    if not marp_md.strip():
        issues.append("Marp 마크다운이 비어 있습니다")
        return {"validation_issues": issues, "iteration_count": state.get("iteration_count", 0) + 1}

    # Frontmatter
    if not marp_md.strip().startswith("---"):
        issues.append("Marp frontmatter 누락: 문서 첫 줄이 --- 이어야 합니다")
    elif "marp: true" not in marp_md[:400]:
        issues.append("marp: true 지시어 누락")

    # Slide count
    slide_count = _count_marp_slides(marp_md)
    if slide_count < 3:
        issues.append(f"슬라이드 수 부족: {slide_count}장 (최소 3장 필요)")
    elif slide_count > 12:
        issues.append(f"슬라이드 수 초과: {slide_count}장 (최대 12장, {slide_count - 12}장 삭제 필요)")
        
    # Density & Structural checks
    content = re.sub(r'^---\n.*?\n---\n?', '', marp_md.strip(), count=1, flags=re.DOTALL)
    parts = re.split(r'\n---\n', content)
    for idx, part in enumerate(parts):
        has_image = "![bg" in part
        is_section = "<!-- _class: section -->" in part
        is_lead = "<!-- _class: lead -->" in part
        has_table = bool(re.search(r'^\|.+\|', part, re.MULTILINE))
        has_code = "```" in part
        has_columns = '<div class="columns">' in part

        lines = [l for l in part.strip().split('\n') if l.strip()]
        line_count = len(lines)
        bullet_count = len(re.findall(r'^\s*[-*+]\s+', part, re.MULTILINE))

        if is_section:
            if line_count > 4:
                issues.append(f"섹션 슬라이드 {idx+1} 내용 과다: 제목만 있어야 합니다.")
            continue

        if is_lead:
            continue

        # Minimum density check for content slides
        if not is_section and not is_lead and line_count < 8:
            issues.append(f"슬라이드 {idx+1} 내용 부족: {line_count}줄 (최소 8줄 필요). 더 많은 세부 정보, 예시 코드, 경고 메모를 추가하세요.")

        # Hard cap only for pure text slides without structured layouts
        if not (has_table or has_code or has_columns or has_image):
            if line_count > 14:
                issues.append(f"슬라이드 {idx+1} 텍스트 과다: {line_count}행. 테이블이나 2단 레이아웃으로 정리하세요.")
            if bullet_count > 7:
                issues.append(f"슬라이드 {idx+1} 불렛 과다: {bullet_count}개. 테이블이나 번호 목록으로 전환하세요.")
        elif has_image and not (has_table or has_columns):
            # Image + plain text: keep it readable
            if line_count > 10:
                issues.append(f"이미지 슬라이드 {idx+1} 내용 과다: {line_count}행 (최대 10행).")

    # Structural checks
    if "<!-- _class: lead -->" not in marp_md:
        issues.append("커버 슬라이드 누락: 첫 번째 슬라이드에 <!-- _class: lead --> 를 추가하고, 제목/부제목을 포함하세요. class: 는 YAML 프론트매터가 아닌 슬라이드 본문에 HTML 주석으로 작성해야 합니다.")

    h2_count = len(re.findall(r'^## .+', marp_md, re.MULTILINE))
    if h2_count < 2:
        issues.append(f"콘텐츠 슬라이드 부족: ## 헤딩이 {h2_count}개 (최소 2개 필요)")

    iteration_count = state.get("iteration_count", 0) + 1
    return {"validation_issues": issues, "iteration_count": iteration_count}
