"""Render the v1.1 research brief from markdown to PDF.

Pipeline:
    brief_v1_1.md → markdown library → HTML → weasyprint → PDF

The rendered PDF is the shipping artifact delivered to institutional clients
(Citadel, Squarepoint, Final) in Phase 6.

Run from backend/:
    venv/bin/python -m exports.brief_pdf
    venv/bin/python -m exports.brief_pdf --md <path> --output <path>

Dependencies:
    markdown>=3.5
    weasyprint>=61.0
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import markdown as md_lib
from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

DEFAULT_MD = Path("../.paul/phases/05-research-brief-pdf/brief_v1_1.md")
DEFAULT_CSS = Path("exports/brief.css")
DEFAULT_OUT = Path("../.paul/phases/05-research-brief-pdf/LookInsight_Insider_Conviction_Signals.pdf")


def slugify(text: str) -> str:
    """Convert heading text to a URL-safe id."""
    text = re.sub(r"<[^>]+>", "", text)  # strip inline HTML
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    text = re.sub(r"\s+", "-", text.strip())
    return text[:80]


def ensure_heading_ids(html: str) -> tuple[str, list[dict]]:
    """Ensure every h2/h3/h4 has an id attribute; return augmented HTML and heading list."""
    headings: list[dict] = []
    seen: set[str] = set()

    def _patch(match: re.Match) -> str:
        level = int(match.group(1))
        attrs = match.group(2) or ""
        inner = match.group(3)

        id_match = re.search(r'id="([^"]+)"', attrs)
        if id_match:
            hid = id_match.group(1)
        else:
            base = slugify(inner) or f"section-{len(headings)+1}"
            hid = base
            i = 2
            while hid in seen:
                hid = f"{base}-{i}"
                i += 1
            attrs = (attrs + f' id="{hid}"').strip()
        seen.add(hid)
        headings.append({"level": level, "id": hid, "text": re.sub(r"<[^>]+>", "", inner).strip()})
        return f"<h{level} {attrs}>{inner}</h{level}>"

    patched = re.sub(
        r"<h([234])([^>]*)>(.*?)</h\1>",
        _patch,
        html,
        flags=re.DOTALL,
    )
    return patched, headings


def build_toc_html(headings: list[dict]) -> str:
    """Build a nested <ol>-based TOC from h2/h3 headings (skip h4 to keep TOC clean)."""
    lines: list[str] = ['<nav class="toc">']
    lines.append("<ol>")
    in_h3_list = False

    for h in headings:
        if h["level"] == 2:
            if in_h3_list:
                lines.append("</ol></li>")
                in_h3_list = False
            lines.append(f'<li><a href="#{h["id"]}">{h["text"]}</a>')
            lines.append("")  # placeholder; will close after next h2 or end
        elif h["level"] == 3:
            if not in_h3_list:
                lines.append("<ol>")
                in_h3_list = True
            lines.append(f'<li><a href="#{h["id"]}">{h["text"]}</a></li>')
        # h4 intentionally skipped — §5.7's Month-Year subheadings would flood the TOC

    if in_h3_list:
        lines.append("</ol></li>")
    else:
        # close the last open <li> from a bare h2
        if lines[-1] == "":
            lines[-1] = "</li>"

    lines.append("</ol>")
    lines.append("</nav>")
    return "\n".join(lines)


def split_cover(html: str) -> tuple[str, str]:
    """Split HTML at the first NUMBERED section heading (e.g., `## 1. Executive Summary`).

    The brief's first h2 is a subtitle (`## A Methodology and Performance Brief (v1.1)`)
    which belongs on the cover page, not in the body section. Numbered sections start with
    a digit: `<h2>1. Executive Summary</h2>`, `<h2>2. Thesis</h2>`, etc.
    """
    m = re.search(r"<h2[^>]*>\s*\d", html)
    if not m:
        # fallback: first h2 if no numbered headings exist
        m = re.search(r"<h2\b", html)
        if not m:
            return html, ""
    return html[: m.start()], html[m.start():]


def wrap_html(cover_html: str, toc_html: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>LookInsight — Insider Conviction Signals</title>
</head>
<body>
  <section class="cover">
{cover_html}
  </section>
  <section class="toc-page">
    <h2>Table of Contents</h2>
{toc_html}
  </section>
  <section class="body">
{body_html}
  </section>
</body>
</html>
"""


def render_pdf(md_path: Path, css_path: Path, out_path: Path) -> None:
    logger.info("Reading markdown: %s", md_path)
    src = md_path.read_text(encoding="utf-8")

    md = md_lib.Markdown(extensions=["tables", "fenced_code", "attr_list"])
    html = md.convert(src)

    html, headings = ensure_heading_ids(html)
    logger.info("Parsed %d headings (h2/h3/h4)", len(headings))

    cover_html, body_html = split_cover(html)

    # TOC only includes sections that appear in the body (numbered sections) —
    # this excludes the cover subtitle.
    body_heading_ids = set(re.findall(r'id="([^"]+)"', body_html))
    toc_headings = [
        h for h in headings
        if h["level"] in (2, 3) and h["id"] in body_heading_ids
    ]
    toc_html = build_toc_html(toc_headings)

    full_html = wrap_html(cover_html, toc_html, body_html)

    base_url = str(md_path.parent.resolve())
    logger.info("Rendering PDF via weasyprint (base_url=%s)", base_url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html, base_url=base_url).write_pdf(
        target=str(out_path),
        stylesheets=[CSS(filename=str(css_path))],
    )
    logger.info("Wrote PDF: %s (%.1f KB)", out_path, out_path.stat().st_size / 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render v1.1 brief to PDF")
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--css", type=Path, default=DEFAULT_CSS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.md.exists():
        logger.error("Markdown source not found: %s", args.md)
        return 1
    if not args.css.exists():
        logger.error("CSS stylesheet not found: %s", args.css)
        return 1

    render_pdf(args.md, args.css, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
