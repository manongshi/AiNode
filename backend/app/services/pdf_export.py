"""使用 Chromium 原生打印能力导出笔记 PDF。"""

from html import escape
from pathlib import Path

import markdown
from playwright.async_api import async_playwright

from app.config import settings
from app.schemas import NoteGenerateResponse


class PdfExportError(RuntimeError):
    pass


class NotePdfService:
    """将保存的笔记放进 PDF 专用 HTML，再交由 Chromium 分页打印。"""

    async def export(self, note: NoteGenerateResponse) -> bytes:
        html = self._build_html(note)
        executable_path = settings.pdf_chromium_executable
        if executable_path and not Path(executable_path).exists():
            executable_path = ""

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    executable_path=executable_path or None,
                )
                try:
                    page = await browser.new_page(viewport={"width": 1240, "height": 1754})
                    await page.set_content(html, wait_until="networkidle")
                    return await page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "16mm", "right": "16mm", "bottom": "18mm", "left": "16mm"},
                    )
                finally:
                    await browser.close()
        except Exception as exc:
            raise PdfExportError("PDF 生成失败，请确认本机 Chrome 可正常启动") from exc

    @staticmethod
    def _build_html(note: NoteGenerateResponse) -> str:
        document = markdown.markdown(
            note.note or "",
            extensions=["extra", "sane_lists", "nl2br"],
            output_format="html5",
        )
        title = escape(note.video.title or "AI 笔记")
        subtitle = escape(f"视频笔记 · {note.contentType}")
        mind_map = NotePdfService._build_mind_map_html(note.mindMap)
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <style>
    @page {{ size: A4; margin: 16mm 16mm 18mm; }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; color: #183d30; background: #fff; font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; }}
    article {{ width: 100%; }}
    .eyebrow {{ color: #258d68; font-size: 10pt; font-weight: 800; letter-spacing: 1.8pt; }}
    h1 {{ margin: 13pt 0 8pt; padding-bottom: 13pt; color: #174333; border-bottom: 1.6pt solid #2c966f; font-size: 25pt; line-height: 1.35; }}
    .meta {{ margin: 0 0 25pt; color: #6f8e82; font-size: 10pt; }}
    .mind-map {{ margin: 0 0 30pt; padding: 16pt; background: #f6faf8; border: 1px solid #d9e9e1; border-radius: 9pt; }}
    .mind-map-heading {{ display: flex; align-items: center; gap: 7pt; margin-bottom: 14pt; color: #1e7758; font-size: 12pt; font-weight: 800; }}
    .mind-map-heading::before {{ width: 8pt; height: 8pt; background: #2c966f; border-radius: 50%; content: ""; }}
    .mind-map-root {{ width: max-content; max-width: 85%; margin: 0 auto 15pt; padding: 8pt 15pt; color: #fff; background: #1f7557; border-radius: 999px; font-size: 12pt; font-weight: 800; text-align: center; }}
    .mind-map-branches {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10pt; align-items: start; }}
    .mind-map-branch {{ position: relative; padding: 10pt 11pt; background: #fff; border: 1px solid #dbeae3; border-top: 3pt solid #63b596; border-radius: 6pt; break-inside: auto; page-break-inside: auto; }}
    .mind-map-branch h3 {{ margin: 0 0 7pt; color: #226d52; font-size: 11pt; line-height: 1.45; }}
    .mind-map-list {{ margin: 0; padding-left: 12pt; border-left: 1px solid #bcdacb; list-style: none; }}
    .mind-map-list .mind-map-list {{ margin-top: 3pt; margin-left: 2pt; border-left-color: #d9e9e1; }}
    .mind-map-list li {{ position: relative; margin: 4pt 0; color: #41685a; font-size: 8.6pt; line-height: 1.48; break-inside: avoid; page-break-inside: avoid; }}
    .mind-map-list li::before {{ position: absolute; top: .65em; left: -12.5pt; width: 7pt; height: 1px; background: #bcdacb; content: ""; }}
    .mind-map-empty {{ margin: 0; color: #789187; font-size: 9.5pt; text-align: center; }}
    .document-start {{ margin-top: 0; padding-top: 2pt; }}
    h2 {{ margin: 27pt 0 13pt; padding-left: 11pt; color: #174333; border-left: 4pt solid #2c966f; font-size: 19pt; line-height: 1.35; break-after: avoid-page; page-break-after: avoid; }}
    h3 {{ margin: 20pt 0 10pt; color: #245b47; font-size: 15pt; line-height: 1.4; break-after: avoid-page; page-break-after: avoid; }}
    h4 {{ margin: 16pt 0 8pt; color: #2e6e57; font-size: 12pt; break-after: avoid-page; page-break-after: avoid; }}
    p, li {{ color: #355b4d; font-size: 11pt; line-height: 1.9; }}
    p {{ margin: 0 0 10pt; orphans: 3; widows: 3; }}
    ul, ol {{ margin: 7pt 0 12pt; padding-left: 22pt; }}
    li {{ margin: 3pt 0; }}
    blockquote {{ margin: 15pt 0; padding: 8pt 14pt; color: #527569; background: #f0f8f3; border-left: 3pt solid #8bcaae; break-inside: avoid-page; page-break-inside: avoid; }}
    pre {{ padding: 12pt; overflow: hidden; background: #f4f6f5; font-size: 9pt; white-space: pre-wrap; break-inside: avoid-page; page-break-inside: avoid; }}
    table {{ width: 100%; margin: 12pt 0; border-collapse: collapse; font-size: 10pt; break-inside: avoid-page; page-break-inside: avoid; }}
    th, td {{ padding: 7pt; border: 1px solid #dce9e2; text-align: left; vertical-align: top; }}
    th {{ background: #f0f8f3; }}
    img {{ max-width: 100%; break-inside: avoid-page; page-break-inside: avoid; }}
  </style>
</head>
<body>
  <article>
    <div class="eyebrow">AI NOTE</div>
    <h1>{title}</h1>
    <p class="meta">{subtitle}</p>
    {mind_map}
    <section class="document-start">{document}</section>
  </article>
</body>
</html>"""

    @staticmethod
    def _build_mind_map_html(mind_map: dict | None) -> str:
        if not isinstance(mind_map, dict) or not str(mind_map.get("content") or "").strip():
            return """
            <section class="mind-map">
              <div class="mind-map-heading">思维导图</div>
              <p class="mind-map-empty">这篇笔记暂未生成思维导图。</p>
            </section>
            """

        def render_children(children, depth: int = 0) -> str:
            if not isinstance(children, list) or not children:
                return ""
            items = []
            for child in children:
                if not isinstance(child, dict):
                    continue
                content = str(child.get("content") or "").strip()
                if not content:
                    continue
                nested = render_children(child.get("children"), depth + 1)
                items.append(f"<li><span>{escape(content)}</span>{nested}</li>")
            return f'<ul class="mind-map-list depth-{depth}">{"".join(items)}</ul>' if items else ""

        branches = []
        for branch in mind_map.get("children") or []:
            if not isinstance(branch, dict):
                continue
            branch_title = str(branch.get("content") or "").strip()
            if not branch_title:
                continue
            branches.append(
                f'<section class="mind-map-branch"><h3>{escape(branch_title)}</h3>'
                f'{render_children(branch.get("children"))}</section>'
            )

        root = escape(str(mind_map.get("content") or "思维导图").strip())
        branch_html = "".join(branches) or '<p class="mind-map-empty">暂无可展示的分支内容。</p>'
        return f"""
        <section class="mind-map">
          <div class="mind-map-heading">思维导图</div>
          <div class="mind-map-root">{root}</div>
          <div class="mind-map-branches">{branch_html}</div>
        </section>
        """
