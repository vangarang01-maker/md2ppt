import asyncio
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from graph.state import PPTState

BRAND_THEME_NAME = {
    "starbucks": "md2ppt-starbucks",
    "dark_tech":  "md2ppt-dark-tech",
    "minimal":    "md2ppt-minimal",
    "corporate":  "md2ppt-corporate",
    "default":    "md2ppt-default",
}

_SYSTEM = """You are a senior presentation architect. Your job is to convert source documents into DENSE, information-rich Marp slides.
Output ONLY raw Marp markdown — no code fences, no explanation, nothing before the opening ---.

## DENSITY IS THE TOP PRIORITY
Every content slide must be FILLED. Sparse slides (3 bullets, nothing else) are a failure.
Use ALL data in the source: every code, name, step, date, note, file path, and warning.

## Layout Patterns — CHOOSE THE RIGHT ONE FOR EACH SLIDE

### Pattern A — Table (use for: mappings, org codes, steps with attributes, comparisons)
## 슬라이드 제목
> 이 테이블이 보여주는 것을 한 줄로 설명.

| 컬럼A | 컬럼B | 컬럼C |
|-------|-------|-------|
| 값1   | 값2   | 값3   |
| 값4   | 값5   | 값6   |

**주의**: 중요한 보충 설명.

### Pattern B — Two Columns (use for: before/after, cause/effect, WHO does WHAT)
## 슬라이드 제목
<div class="columns">
<div>

**왼쪽 헤더**
- 항목 A
- 항목 B
- 항목 C

</div>
<div>

**오른쪽 헤더**
- 항목 X
- 항목 Y
- 항목 Z

</div>
</div>

### Pattern C — Numbered Action List (use for: checklists, ordered procedures)
## 슬라이드 제목
**01** 첫 번째 액션 — 구체적인 설명 `코드_참조`
**02** 두 번째 액션 — 구체적인 설명
**03** 세 번째 액션 — 구체적인 설명
**04** 네 번째 액션 — 구체적인 설명

> ⚠️ **주의**: 중요 경고 또는 검증 사항.

### Pattern D — Code Diff (use for: source code changes, before/after logic)
## 슬라이드 제목
> 파일: `경로/파일명.js`

```diff
+ if (orgCode === 'NEW001') allowAccess = true;   // 신설
- if (orgCode === 'OLD001') {{ ... }}              // 폐쇄
  if (deptName === '구 이름') → '새 이름'           // 변경
```

**작업 건수**: 신설 +1, 폐쇄 -2, 명칭 변경 7건

### Pattern E — Metadata Table (use for: system info, participants, schedule)
## 슬라이드 제목
| 항목 | 내용 |
|------|------|
| **System** | MPP |
| **대상 파일** | src/.../gisCommon.js |
| **배포 일시** | 2026.03.20 11:00 |
| **담당자** | 최남우 / 이화성 |

## EXACT Required Output Format (DO NOT DEVIATE)

The output MUST start with this EXACT 4-line frontmatter block — nothing else allowed before the first slide:

```
---
marp: true
theme: {theme_name}
paginate: true
---
```

Then IMMEDIATELY the first slide (cover), like this:

```
<!-- _class: lead -->
# 제목
## 부제목

---

## 목차
| # | 섹션 | 내용 |
|---|------|------|
| 01 | 섹션A | ... |
...

---

## 콘텐츠 슬라이드
[내용]

---

<!-- _class: section -->
# Q&A
```

## Structural Rules
1. **Frontmatter**: ONLY `marp: true`, `theme: {theme_name}`, `paginate: true` — NO `class:` in frontmatter.
2. **Cover slide class**: MUST use `<!-- _class: lead -->` as HTML comment ON ITS OWN LINE, BEFORE the `#` title.
3. **Total slides**: exactly {slide_count} (max 12). Count `---` separators carefully.
4. **Fill each slide (MANDATORY)**: Each content slide MUST have at least 10 non-empty lines of content (excluding h2 heading and blank lines). If below 10 lines, expand with:
   - Sub-details for each item (exact codes, file paths, names, dates)
   - A warning/note blockquote
   - An additional table row or column showing related info
   - The "why" behind each action
5. **Section slides** (`<!-- _class: section -->`): title + optional subtitle. Use MAX 1 time.
6. **Image syntax**: `![bg right:40%](URL)` MUST be the VERY FIRST LINE after `---`.
7. **Language**: same as input content.
8. **No mermaid diagrams** — Marp CLI cannot render them.

{validation_fix}"""

_USER = """## Presentation Direction
{direction}

## Source Content
{md_content}"""


def _make_llm(model: str, api_key: str):
    if model == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-6", api_key=api_key, max_tokens=6000)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", google_api_key=api_key, max_output_tokens=16384
    )


def _clean_output(raw: str) -> str:
    text = raw.strip()
    # Strip code fences if the LLM wrapped output
    if text.startswith("```"):
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    text = text.strip()

    # Fix broken frontmatter: if class: or title content is inside YAML frontmatter
    # Pattern: ---\nmarp: true\n...\nclass: lead\n...\n# Title... \n---
    # The issue is no closing --- after frontmatter before first slide content
    fm_match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if fm_match:
        fm_content = fm_match.group(1)
        # Detect if frontmatter has non-YAML content (lines starting with # followed by space = heading)
        fm_lines = fm_content.split('\n')
        yaml_lines = []
        slide_lines = []
        in_slide = False
        for line in fm_lines:
            if not in_slide and re.match(r'^(marp:|theme:|paginate:|size:|title:|description:|author:|keywords:|class:)', line):
                if not line.startswith('class:'):  # Remove class: from frontmatter
                    yaml_lines.append(line)
            elif not in_slide and line.strip() == '':
                pass  # skip blank lines in frontmatter
            else:
                in_slide = True
                slide_lines.append(line)

        if slide_lines:
            # Rebuild: proper frontmatter + extracted slide content
            new_fm = '---\n' + '\n'.join(yaml_lines) + '\n---\n\n'
            # If there was class: lead content, add it as proper directive
            had_lead = any(l.strip() == 'class: lead' for l in fm_lines)
            slide_content = '\n'.join(slide_lines).strip()
            if had_lead and not slide_content.startswith('<!-- _class: lead -->'):
                slide_content = '<!-- _class: lead -->\n' + slide_content
            rest = text[fm_match.end():]
            text = new_fm + slide_content + '\n\n---\n' + rest if rest.strip() else new_fm + slide_content

    return text


def _extract_title(marp_md: str) -> str:
    m = re.search(r'^# (.+)$', marp_md, re.MULTILINE)
    return m.group(1).strip() if m else "Slides"


async def node_outline_planner(state: PPTState) -> dict:
    direction = state.get("direction", {})
    design_system = state.get("design_system", {})
    validation_issues = state.get("validation_issues", [])

    brand = design_system.get("brand", "default")
    theme_name = BRAND_THEME_NAME.get(brand, "md2ppt-default")
    slide_count = min(int(direction.get("slide_count", 9)), 12)

    validation_fix = ""
    if validation_issues:
        items = "\n".join(f"  - {issue}" for issue in validation_issues)
        validation_fix = f"\n11. FIX THESE ISSUES from previous attempt:\n{items}"

    llm = _make_llm(state["model"], state["api_key"])
    chain = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", _USER),
    ]) | llm | StrOutputParser()

    raw = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: chain.invoke({
            "theme_name": theme_name,
            "slide_count": slide_count,
            "validation_fix": validation_fix,
            "direction": str(direction),
            "md_content": state["md_content"][:10000],
        }),
    )

    marp_md = _clean_output(raw)
    title = _extract_title(marp_md)

    return {
        "marp_md": marp_md,
        "slides_data": {"title": title, "brand": brand},
    }
