import json
import re

SYSTEM_PROMPT = """You are a presentation designer. Analyze the given markdown content and return a structured slide plan as valid JSON only — no explanation, no markdown fences.

JSON schema:
{
  "title": "string",
  "slides": [
    { "type": "title",   "title": "string", "subtitle": "string" },
    { "type": "content", "title": "string", "bullets": ["string"] },
    { "type": "chart",   "title": "string", "chart_type": "bar|column|line|pie",
      "categories": ["string"], "series": [{"name": "string", "values": [number]}] }
  ]
}

Rules:
- Maximum 10 slides total
- First slide must be type "title"
- Use "chart" type when markdown contains tables or numeric comparison data
- Keep bullets concise (max 6 per slide)
- Respond in the same language as the input content
"""


async def structure_slides(content: str, model: str, api_key: str, design: str) -> dict:
    prompt = f"[디자인 힌트: {design}]\n\n{content}" if design else content

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


async def _call_gemini(prompt: str, api_key: str) -> dict:
    from google import genai
    from google.genai.types import GenerateContentConfig
    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
        config=GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return _parse_json(response.text)


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("LLM이 유효한 JSON을 반환하지 않았습니다")
    return json.loads(match.group())
