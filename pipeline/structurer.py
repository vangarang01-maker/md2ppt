import json
import re
from typing import Literal

# ── Step 1: Content Analysis Prompt ────────────────────────────────────────
_ANALYSIS_SYSTEM = """You are a presentation strategist. Analyze the given content and extract a structured brief for a slide deck author.

Output ONLY valid JSON — no markdown fences, no explanation.

{{
  "core_message": "The single most important takeaway (1 sentence)",
  "narrative_arc": "How the story should flow (2-3 sentences)",
  "key_sections": [
    {{
      "title": "Section title (concise, punchy)",
      "focus": "What this section must convey",
      "best_slide_type": "bento|stat|chart|two_column|quote|flowchart",
      "data_points": ["specific numbers, facts, or comparisons to highlight"]
    }}
  ],
  "quantitative_data": [
    {{"label": "metric name", "value": "number or %", "context": "what it means"}}
  ],
  "recommended_flow": ["title", "agenda", "section: X", "...", "summary"]
}}

Rules:
- key_sections: 2~3 sections only
- Extract ALL numeric data from the source — do not omit any numbers
- best_slide_type: choose based on data nature (chart if 3+ comparable numbers, stat for KPIs, etc.)
- Respond in the same language as the input content
"""

# ── Step 2: Slide Builder Prompt ────────────────────────────────────────────
_BUILD_SYSTEM = """You are an expert slide deck author. You receive a strategic brief and the original content.
Build the final slide JSON exactly following the brief's narrative arc.

Output ONLY valid JSON — no markdown fences, no explanation.

{{
  "theme": {{
    "bg": "#hex", "surface": "#hex", "accent": "#hex",
    "text": "#hex", "subtext": "#hex", "body": "#hex"
  }},
  "title": "string",
  "slides": [
    {{ "type": "title",      "title": "string", "subtitle": "string" }},
    {{ "type": "agenda",     "title": "string", "items": ["string"] }},
    {{ "type": "section",    "title": "string", "subtitle": "string", "icon": "mdi:icon-name" }},
    {{ "type": "stat",       "title": "string", "stats": [{{"label": "string", "value": "string", "icon": "mdi:icon-name"}}] }},
    {{ "type": "two_column", "title": "string", "left": {{"heading": "string", "bullets": ["string"]}}, "right": {{"heading": "string", "bullets": ["string"]}} }},
    {{ "type": "quote",      "title": "string", "quote": "string", "attribution": "string" }},
    {{ "type": "chart",      "title": "string", "chart_type": "bar|column|line|pie",
      "categories": ["string"], "series": [{{"name": "string", "values": [0]}}] }},
    {{ "type": "bento",      "title": "string", "cards": [{{"title": "string", "body": "string", "icon": "mdi:icon-name"}}] }},
    {{ "type": "flowchart",  "title": "string", "steps": [{{"label": "string", "detail": "string", "icon": "mdi:icon-name"}}] }},
    {{ "type": "summary",    "title": "string", "bullets": ["string"] }}
  ]
}}

STRICT RULES:
1. Follow the recommended_flow from the brief EXACTLY.
2. MAXIMUM 7 slides total. Pack all data points — do NOT omit information.
3. REWRITE content in punchy presentation language. Never copy-paste source sentences.
4. NO BULLET-LIST SLIDES. NEVER output type:"content". Every informational slide MUST be: bento, stat, chart, two_column, or quote.

5. SLIDE TYPE SELECTION:
   chart      → ANY trend, ranking, comparison, distribution, before/after, or 3+ data points
   stat       → 2~3 standalone KPIs (short values: "47%", "3.2×", "12건")
   two_column → comparison, before/after, pros/cons
   bento      → 4~6 feature/finding cards (title ≤6 words, body ≤45 words, + icon)
   flowchart  → sequential process, step-by-step procedure, pipeline, or workflow (3~5 ordered steps)
   quote      → single most important insight

6. CHART rules: chart_type "column" for comparisons, "bar" for rankings, "line" for trends, "pie" for part-of-whole.
   categories: 3~7 items. series values MUST be real numbers. Estimate plausible values if exact numbers unknown.

7. STAT rules: 2~3 stats max. value MUST be short number string. NEVER use sentences as value.

8. two_column: each side MUST have 5~7 bullets.

9. summary: 4~5 bullets each starting with a relevant emoji.

10. AGENDA ↔ SECTION CONSISTENCY: agenda items MUST be EXACTLY the same text as section slide titles.

11. THEME: match the theme description if provided. Default dark navy: bg=#1A1A2E, surface=#16213E, accent=#4D9DFF, text=#FFFFFF, subtext=#AABBCC, body=#DDEEFF

12. ICONS: every section and bento card must have "icon" (mdi: prefix). Every stat item must have "icon".

13. FLOWCHART rules: 3~5 steps only. Each step: label (≤8 words), detail (≤35 words), icon (mdi: prefix).
    Use when the content describes an ordered process or sequential workflow.

14. Respond in the same language as the input content.
"""


# ── LangChain Chain Builder ─────────────────────────────────────────────────

def _build_langchain_chain(llm):
    """Build a two-step LCEL chain: analyze → build slides."""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.runnables import RunnablePassthrough, RunnableLambda

    analysis_prompt = ChatPromptTemplate.from_messages([
        ("system", _ANALYSIS_SYSTEM),
        ("human", "{input}"),
    ])

    build_prompt = ChatPromptTemplate.from_messages([
        ("system", _BUILD_SYSTEM),
        ("human", "## Strategic Brief\n{brief}\n\n## Original Content\n{original}"),
    ])

    parser = JsonOutputParser()

    def format_brief(data: dict) -> dict:
        return {
            "brief": json.dumps(data, ensure_ascii=False, indent=2),
            "original": data.get("_original", ""),
        }

    analysis_chain = analysis_prompt | llm | parser
    build_chain = build_prompt | llm | parser

    def run_two_step(inputs: dict) -> dict:
        brief = analysis_chain.invoke({"input": inputs["input"]})
        brief["_original"] = inputs["input"]
        return build_chain.invoke(format_brief(brief))

    return RunnableLambda(run_two_step)


def _make_llm_claude(api_key: str):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=api_key,
        max_tokens=4096,
    )


def _make_llm_gemini(api_key: str):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=api_key,
        max_output_tokens=4096,
    )


# ── Public API (unchanged signature) ────────────────────────────────────────

async def structure_slides(
    content: str,
    model: str,
    api_key: str,
    theme_desc: str,
    goal: str,
    audience: str,
) -> dict:
    context_lines = []
    if goal:
        context_lines.append(f"[발표 목적: {goal}]")
    if audience:
        context_lines.append(f"[청중: {audience}]")
    if theme_desc:
        context_lines.append(f"[테마 설명: {theme_desc}]")

    header = "\n".join(context_lines)
    prompt = f"{header}\n\n{content}" if header else content

    if model == "claude":
        llm = _make_llm_claude(api_key)
    else:
        llm = _make_llm_gemini(api_key)

    chain = _build_langchain_chain(llm)

    # LangChain invoke is sync; run in thread to keep FastAPI async
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: chain.invoke({"input": prompt})
    )
    return result
