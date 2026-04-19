import json
import re

SYSTEM_PROMPT = """You are an expert presentation consultant. Your job is to transform raw markdown content into a compelling, narrative-driven slide deck. You do NOT copy-paste — you rewrite everything in crisp presentation voice.

Output ONLY valid JSON with no explanation and no markdown fences.

JSON schema:
{
  "theme": {
    "bg": "#hex",
    "surface": "#hex",
    "accent": "#hex",
    "text": "#hex",
    "subtext": "#hex",
    "body": "#hex"
  },
  "title": "string",
  "slides": [
    { "type": "title",      "title": "string", "subtitle": "string" },
    { "type": "agenda",     "title": "string", "items": ["string"] },
    { "type": "section",    "title": "string", "subtitle": "string", "icon": "mdi:icon-name" },
    { "type": "content",    "title": "string", "icon": "mdi:icon-name", "bullets": ["string"] },
    { "type": "stat",       "title": "string", "stats": [{"label": "string", "value": "string", "icon": "mdi:icon-name"}] },
    { "type": "two_column", "title": "string", "left": {"heading": "string", "bullets": ["string"]}, "right": {"heading": "string", "bullets": ["string"]} },
    { "type": "quote",      "title": "string", "quote": "string", "attribution": "string" },
    { "type": "chart",      "title": "string", "chart_type": "bar|column|line|pie",
      "categories": ["string"], "series": [{"name": "string", "values": [0]}] },
    { "type": "summary",    "title": "string", "bullets": ["string"] }
  ]
}

STRICT RULES:
1. NARRATIVE ARC — slides must follow this order:
   title → agenda → (section + 1~2 content/stat/two_column/quote) × 2~3 groups → summary
2. MAXIMUM 8 slides total. Quality over quantity.
3. REWRITE all content in punchy presentation language. Never copy-paste sentences from source.
4. Each bullet: max 15 words. Start with a relevant emoji (e.g. ⚡ 🔍 ✅ ⚠️ 📊 🎯 🔧 💡 🚀).
5. Max 3 bullets per content/summary slide.
6. Use "stat" type ONLY when real numeric/percentage/ratio data exists. stat "value" MUST be a short number or measure (e.g. "47%", "3.2×", "12건", "1일", "99.9%"). NEVER put long text or sentences as a stat value. If no meaningful numeric data exists, use "content" or "two_column" instead.
7. Use "two_column" for comparisons, before/after, or pros/cons.
8. Use "quote" for the single most important insight or guiding principle.
9. agenda "items" should list section titles only (max 5 items).
10. THEME: Generate a hex color palette that matches the theme description provided.
    If no theme description is given, use this dark navy default:
    bg=#1A1A2E, surface=#16213E, accent=#4D9DFF, text=#FFFFFF, subtext=#AABBCC, body=#DDEEFF
11. ICONS: Add an "icon" field to every section and content slide using MDI icon names (prefix "mdi:").
    For stat slides, add "icon" to each stat item. Choose icons that match the content.
    Examples: "mdi:database", "mdi:cog-outline", "mdi:chart-timeline-variant", "mdi:account-group",
    "mdi:alert-circle-outline", "mdi:check-circle-outline", "mdi:rocket-launch-outline",
    "mdi:shield-check-outline", "mdi:lightning-bolt", "mdi:trending-up", "mdi:layers-outline"
12. Respond in the same language as the input content.
"""


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
        return await _call_claude(prompt, api_key)
    return await _call_gemini(prompt, api_key)


async def _call_claude(prompt: str, api_key: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(msg.content[0].text)


_GEMINI_PRIMARY = "gemini-3.1-flash-lite-preview"
_GEMINI_FALLBACK = "gemini-2.5-flash-lite"


def _is_overload(e: Exception) -> bool:
    msg = str(e).lower()
    return "503" in str(e) or "unavailable" in msg or "high demand" in msg or "overloaded" in msg


async def _call_gemini(prompt: str, api_key: str) -> dict:
    from google import genai
    from google.genai.types import GenerateContentConfig
    client = genai.Client(api_key=api_key)

    for model in [_GEMINI_PRIMARY, _GEMINI_FALLBACK]:
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            return _parse_json(response.text)
        except Exception as e:
            if _is_overload(e) and model == _GEMINI_PRIMARY:
                continue
            raise


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("LLM이 유효한 JSON을 반환하지 않았습니다")
    return json.loads(match.group())
