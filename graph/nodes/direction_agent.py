import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from graph.state import PPTState


_SYSTEM = """You are a presentation strategist. Analyze the given content and extract the optimal presentation direction.

Output ONLY valid JSON — no markdown fences, no explanation.

{{
  "audience": "who this presentation is for (be specific)",
  "tone": "formal|casual|technical|energetic",
  "brand": "starbucks|dark_tech|minimal|corporate|default",
  "slide_count": 7,
  "language": "ko|en",
  "core_message": "single most important takeaway (1 sentence)",
  "narrative_arc": "how the story should flow (2-3 sentences)",
  "key_sections": ["section title 1", "section title 2", "section title 3"]
}}

Brand selection guide:
- starbucks: content related to Starbucks, coffee, or green brand identity
- dark_tech: technical content, data engineering, AI/ML, DevOps topics
- minimal: clean simple content, academic or design-focused
- corporate: business reports, formal executive presentations
- default: dark navy theme, general purpose

Rules:
- If user provided audience or goal hints, incorporate them
- slide_count: 7~12 based on content volume. Complex technical/operational docs should use 10-12.
- key_sections: 2~4 main section titles only
- Respond with string values in the same language as the input content
"""

_USER = """## User Context
Goal: {goal}
Audience: {audience_hint}
Theme: {theme_hint}

## Content
{md_content}"""


def _make_llm(model: str, api_key: str):
    if model == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-haiku-4-5-20251001", api_key=api_key, max_tokens=1024)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite-preview", google_api_key=api_key, max_output_tokens=1024)


async def node_direction_agent(state: PPTState) -> dict:
    llm = _make_llm(state["model"], state["api_key"])
    chain = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", _USER),
    ]) | llm | JsonOutputParser()

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: chain.invoke({
            "goal": state.get("goal", ""),
            "audience_hint": state.get("audience_hint", ""),
            "theme_hint": state.get("theme_hint", ""),
            "md_content": state["md_content"][:8000],
        }),
    )
    return {"direction": result}
