from pathlib import Path

from playwright.async_api import async_playwright


async def screenshot_slides(html_contents: list[str], tmp_dir: str) -> list[str]:
    out = Path(tmp_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 720})

        for i, html in enumerate(html_contents):
            await page.set_content(html, wait_until="networkidle")
            # 폰트 렌더링 완료 대기
            await page.evaluate("document.fonts.ready")
            await page.wait_for_timeout(300)
            path = str(out / f"slide_{i:03d}.png")
            await page.screenshot(
                path=path,
                clip={"x": 0, "y": 0, "width": 1280, "height": 720},
            )
            paths.append(path)

        await browser.close()

    return paths
