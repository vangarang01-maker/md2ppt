import re
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Dark navy theme
_BG = RGBColor(0x1A, 0x1A, 0x2E)
_TEXT = RGBColor(0xFF, 0xFF, 0xFF)
_SUBTEXT = RGBColor(0xAA, 0xBB, 0xCC)
_BODY = RGBColor(0xDD, 0xEE, 0xFF)
_ACCENT = RGBColor(0x4D, 0x9D, 0xFF)

_CHART_TYPE_MAP = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
}


def build_pptx(slides_data: dict, output_dir: str) -> str:
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    for slide in slides_data.get("slides", []):
        t = slide.get("type", "content")
        if t == "title":
            _title_slide(prs, slide)
        elif t == "chart":
            _chart_slide(prs, slide)
        else:
            _content_slide(prs, slide)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w가-힣]", "_", slides_data.get("title", "presentation"))
    out_path = str(Path(output_dir) / f"{safe_name}_{ts}.pptx")
    prs.save(out_path)
    return out_path


def _blank(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _BG
    return slide


def _textbox(slide, left, top, width, height, text, size, bold=False, color=None, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color or _TEXT
    return tf


def _accent_bar(slide, top: float):
    bar = slide.shapes.add_shape(1, Inches(0.8), Inches(top), Inches(1.4), Pt(3))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _ACCENT
    bar.line.fill.background()


def _title_slide(prs, data: dict):
    slide = _blank(prs)
    _textbox(slide, 1, 2.4, 11.33, 1.5, data.get("title", ""), 44, bold=True, align=PP_ALIGN.CENTER)
    subtitle = data.get("subtitle", "")
    if subtitle:
        _textbox(slide, 1, 4.1, 11.33, 1, subtitle, 24, color=_SUBTEXT, align=PP_ALIGN.CENTER)


def _content_slide(prs, data: dict):
    slide = _blank(prs)
    _textbox(slide, 0.8, 0.4, 11.5, 0.9, data.get("title", ""), 32, bold=True)
    _accent_bar(slide, 1.25)

    bullets = data.get("bullets", [])
    if not bullets:
        return
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.5), Inches(5.6))
    tf = box.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets[:6]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(10)
        run = p.add_run()
        run.text = f"•  {bullet}"
        run.font.size = Pt(20)
        run.font.color.rgb = _BODY


def _chart_slide(prs, data: dict):
    slide = _blank(prs)
    _textbox(slide, 0.8, 0.4, 11.5, 0.9, data.get("title", ""), 32, bold=True)
    _accent_bar(slide, 1.25)

    cd = ChartData()
    cd.categories = data.get("categories", ["A", "B", "C"])
    for s in data.get("series", [{"name": "값", "values": [1, 2, 3]}]):
        cd.add_series(s["name"], s["values"])

    chart_type = _CHART_TYPE_MAP.get(data.get("chart_type", "bar"), XL_CHART_TYPE.BAR_CLUSTERED)
    chart_shape = slide.shapes.add_chart(chart_type, Inches(1), Inches(1.6), Inches(11), Inches(5.5), cd)
    chart_shape.chart.has_legend = len(data.get("series", [])) > 1
