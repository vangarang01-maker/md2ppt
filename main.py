import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from pipeline.reader import read_md_files
from pipeline.structurer import structure_slides
from pipeline.pptx_builder import build_pptx
from storage import KeyStore

app = FastAPI(title="MD → PPT 파이프라인")
store = KeyStore()
OUTPUT_DIR = str(Path(__file__).parent / "output")


class SettingsIn(BaseModel):
    claude_key: str = ""
    gemini_key: str = ""


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/settings")
async def get_settings():
    return {"claude": store.has("claude"), "gemini": store.has("gemini")}


@app.post("/api/settings")
async def save_settings(body: SettingsIn):
    if body.claude_key:
        store.save("claude", body.claude_key)
    if body.gemini_key:
        store.save("gemini", body.gemini_key)
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

            yield event(70, "PPT 생성 중...")
            await asyncio.sleep(0.05)

            out_path = await asyncio.to_thread(build_pptx, slides_data, output)

            yield event(100, "완료!", file=out_path)

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
