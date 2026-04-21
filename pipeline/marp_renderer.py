import asyncio
import os
import re
import subprocess
from pathlib import Path

THEMES_DIR = Path(__file__).parent.parent / "themes"

BRAND_CSS = {
    "starbucks": "md2ppt-starbucks.css",
    "dark_tech": "md2ppt-dark-tech.css",
    "minimal":   "md2ppt-minimal.css",
    "corporate": "md2ppt-corporate.css",
    "default":   "md2ppt-default.css",
}

BRAND_THEME_NAME = {
    "starbucks": "md2ppt-starbucks",
    "dark_tech": "md2ppt-dark-tech",
    "minimal":   "md2ppt-minimal",
    "corporate": "md2ppt-corporate",
    "default":   "md2ppt-default",
}


def _safe_filename(title: str) -> str:
    name = re.sub(r'[^\w\s가-힣-]', '', title).strip()[:40]
    return name or "slides"


def _build_env() -> dict:
    env = os.environ.copy()
    homebrew_bin = "/opt/homebrew/bin"
    if homebrew_bin not in env.get("PATH", ""):
        env["PATH"] = homebrew_bin + ":" + env.get("PATH", "")
    return env


def render_marp_sync(marp_md: str, brand: str, output_dir: str, title: str) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    md_path = out / "_slide.md"
    md_path.write_text(marp_md, encoding="utf-8")

    pptx_path = out / f"{_safe_filename(title)}.pptx"

    cmd = [
        "npx", "-y", "@marp-team/marp-cli@latest",
        str(md_path),
        "--theme-set", str(THEMES_DIR),
        "--theme", BRAND_THEME_NAME.get(brand, "md2ppt-default"),
        "--pptx",
        "--html",
        "--allow-local-files",
        "-o", str(pptx_path),
    ]

    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        env=_build_env(),
    )

    if result.returncode != 0:
        raise RuntimeError(f"marp-cli 오류:\n{result.stderr}")

    return str(pptx_path)


async def render_marp(marp_md: str, brand: str, output_dir: str, title: str) -> str:
    return await asyncio.to_thread(render_marp_sync, marp_md, brand, output_dir, title)
