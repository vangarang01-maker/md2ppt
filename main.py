import asyncio
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from pipeline.reader import read_md_files
from pipeline.structurer import structure_slides
from pipeline.html_renderer import render_all_slides
from pipeline.screenshot import screenshot_slides
from pipeline.image_pptx import build_pptx_from_images
from pipeline.icon_fetcher import fetch_icons
from pipeline.image_fetcher import fetch_images
from storage import KeyStore

app = FastAPI(title="MD → PPT 파이프라인")
store = KeyStore()
OUTPUT_DIR = str(Path(__file__).parent / "output")


class SettingsIn(BaseModel):
    claude_key: str = ""
    gemini_key: str = ""
    openai_key: str = ""
    pexels_key: str = ""


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/settings")
async def get_settings():
    return {
        "claude":   store.has("claude"),
        "gemini":   store.has("gemini"),
        "openai":  store.has("openai"),
        "pexels":  store.has("pexels"),
    }


@app.post("/api/settings")
async def save_settings(body: SettingsIn):
    if body.claude_key:
        store.save("claude", body.claude_key)
    if body.gemini_key:
        store.save("gemini", body.gemini_key)
    if body.openai_key:
        store.save("openai", body.openai_key)
    if body.pexels_key:
        store.save("pexels", body.pexels_key)
    return {"status": "ok"}


@app.get("/api/generate")
async def generate(
    folder: str,
    model: str,
    theme: str = "",
    goal: str = "",
    audience: str = "",
    output: str = OUTPUT_DIR,
):
    api_key = store.load(model)
    if not api_key:
        raise HTTPException(400, f"{model} API 키가 설정되지 않았습니다. 설정 탭에서 입력해주세요.")

    async def stream():
        def event(progress: int, message: str, **kwargs):
            data = {"progress": progress, "message": message, **kwargs}
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            yield event(10, ".md 파일 읽는 중...")
            await asyncio.sleep(0.05)

            md_content = await asyncio.to_thread(read_md_files, folder)
            if not md_content:
                yield f"data: {json.dumps({'error': '폴더에 .md 파일이 없습니다'})}\n\n"
                return

            yield event(30, f"LLM({model}) 으로 슬라이드 구조 분석 중...")
            await asyncio.sleep(0.05)

            slides_data = await structure_slides(md_content, model, api_key, theme, goal, audience)

            yield event(50, "아이콘 리소스 로드 중...")
            icons = await fetch_icons(slides_data)

            yield event(58, "배경 이미지 생성 중...")
            openai_key = store.load("openai")
            pexels_key = store.load("pexels")
            images = await fetch_images(slides_data, pexels_key=pexels_key, openai_key=openai_key)

            yield event(66, "슬라이드 HTML 렌더링 중...")
            html_slides = render_all_slides(slides_data, icons, images)

            yield event(75, f"슬라이드 {len(html_slides)}장 스크린샷 캡처 중...")
            await asyncio.sleep(0.05)

            tmp_dir = str(Path(output) / ".tmp_screenshots")
            image_paths = await screenshot_slides(html_slides, tmp_dir)

            yield event(92, "PPT 파일 조립 중...")
            await asyncio.sleep(0.05)

            out_path = await asyncio.to_thread(
                build_pptx_from_images, image_paths, slides_data.get("title", ""), output
            )
            shutil.rmtree(tmp_dir, ignore_errors=True)

            yield event(100, "완료!", file=out_path)

        except Exception as e:
            yield f"data: {json.dumps({'error': _friendly_error(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/generate-v2")
async def generate_v2(
    folder: str,
    model: str,
    theme: str = "",
    goal: str = "",
    audience: str = "",
    output: str = OUTPUT_DIR,
):
    api_key = store.load(model)
    if not api_key:
        raise HTTPException(400, f"{model} API 키가 설정되지 않았습니다. 설정 탭에서 입력해주세요.")

    openai_key = store.load("openai") or ""
    pexels_key = store.load("pexels") or ""

    _NODE_PROGRESS = {
        "file_parser":      (10, ".md 파일 읽는 중..."),
        "direction_agent":  (25, "[Node 2] 발표 방향 분석 중..."),
        "design_selector":  (38, "[Node 3] Marp 디자인 테마 선택 중..."),
        "outline_planner":  (58, "[Node 4] LLM → Marp 슬라이드 마크다운 생성 중..."),
        "layout_validator": (75, "[Node 5] 슬라이드 구조 검증 중..."),
        "final_output":     (88, "Marp CLI → PPTX 렌더링 중..."),
    }

    async def stream():
        def event(progress: int, message: str, **kwargs):
            data = {"progress": progress, "message": message, **kwargs}
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        queue: asyncio.Queue = asyncio.Queue()
        result: dict = {}

        async def run_graph():
            try:
                from graph.graph import build_graph
                initial_state = {
                    "folder": folder, "model": model,
                    "api_key": api_key, "openai_key": openai_key, "pexels_key": pexels_key,
                    "goal": goal, "audience_hint": audience, "theme_hint": theme,
                    "output_dir": output,
                    "md_content": "", "direction": {}, "design_system": {},
                    "marp_md": "", "slides_data": {}, "html_slides": [],
                    "validation_issues": [], "iteration_count": 0, "output_path": "",
                }
                graph = build_graph()
                async for chunk in graph.astream(initial_state):
                    node_name = next(iter(chunk))
                    node_state = chunk[node_name]
                    await queue.put(("progress", node_name, node_state))
                    result.update(node_state)
                await queue.put(("done", None, None))
            except Exception as e:
                await queue.put(("error", str(e), None))

        asyncio.create_task(run_graph())

        while True:
            kind, name, data = await queue.get()
            if kind == "error":
                yield f"data: {json.dumps({'error': _friendly_error(Exception(name))}, ensure_ascii=False)}\n\n"
                break
            if kind == "done":
                yield event(100, "완료!", file=result.get("output_path", ""))
                break
            if name in _NODE_PROGRESS:
                progress, message = _NODE_PROGRESS[name]
                extra = {}
                if name == "layout_validator":
                    issues = data.get("validation_issues", [])
                    count = data.get("iteration_count", 1)
                    if issues:
                        extra["warning"] = f"Marp 검증 이슈 {len(issues)}건 → 재생성 (시도 {count}/3)"
                    else:
                        extra["info"] = "슬라이드 구조 검증 통과"
                yield event(progress, message, **extra)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    m = msg.lower()

    if "503" in msg or "unavailable" in m or "high demand" in m:
        return "AI 서버가 일시적으로 과부하 상태입니다. 잠시 후 다시 시도해주세요. (503 Unavailable)"
    if "429" in msg or "quota" in m or "rate limit" in m or "resource_exhausted" in m:
        return "API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요. (Rate Limit)"
    if "401" in msg or "403" in msg or "invalid api key" in m or "api_key" in m or "unauthenticated" in m:
        return "API 키가 올바르지 않습니다. 설정 탭에서 키를 확인해주세요. (Authentication Error)"
    if "폴더가 존재하지 않습니다" in msg:
        return f"입력한 폴더 경로를 찾을 수 없습니다: {msg}"
    if "유효한 json" in m or "json" in m and "반환하지 않았습니다" in msg:
        return "AI가 슬라이드 구조 생성에 실패했습니다. 다시 시도하거나 다른 모델을 사용해보세요."
    if "marp-cli" in m or "marp" in m and "오류" in msg:
        return f"Marp CLI 렌더링 실패: {msg}\n터미널에서 'npx -y @marp-team/marp-cli@latest --version' 으로 설치를 확인하세요."
    if "executable doesn't exist" in m or "playwright" in m or "chromium" in m or "browser" in m:
        return "Playwright Chromium이 설치되지 않았습니다. 터미널에서 'playwright install chromium' 을 실행해주세요."
    if "connection" in m or "timeout" in m or "timed out" in m:
        return "네트워크 연결 오류가 발생했습니다. 인터넷 연결을 확인하고 다시 시도해주세요."

    return f"오류가 발생했습니다: {msg}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
