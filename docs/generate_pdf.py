"""Convert docs/RAPPORT.md to PDF."""

from __future__ import annotations

import re
from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parent
MD_PATH = ROOT / "RAPPORT.md"
PDF_PATH = ROOT / "RAPPORT.pdf"

CSS = """
@page {
    size: A4;
    margin: 2cm 2.2cm;
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1 {
    font-size: 20pt;
    color: #0f3d5c;
    border-bottom: 2px solid #0f3d5c;
    padding-bottom: 6px;
    margin-top: 0;
}
h2 {
    font-size: 14pt;
    color: #0f3d5c;
    margin-top: 22px;
    page-break-after: avoid;
}
h3 {
    font-size: 11.5pt;
    color: #1f4f6f;
    margin-top: 16px;
    page-break-after: avoid;
}
h4 {
    font-size: 10.5pt;
    margin-top: 12px;
}
p, li {
    text-align: justify;
}
code, pre {
    font-family: Courier, monospace;
    font-size: 8pt;
    background-color: #f4f6f8;
}
pre {
    padding: 8px;
    border: 1px solid #dde3ea;
    white-space: pre;
    line-height: 1.2;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 9pt;
}
th, td {
    border: 1px solid #c8d2dc;
    padding: 5px 7px;
    vertical-align: top;
}
th {
    background-color: #e8eef4;
    font-weight: bold;
}
hr {
    border: none;
    border-top: 1px solid #c8d2dc;
    margin: 18px 0;
}
strong {
    color: #0f3d5c;
}
"""


# Caractères Unicode de dessin absents des polices PDF standard (Courier/Helvetica),
# convertis en ASCII pour conserver l'alignement des schémas dans le PDF.
_BOX_DRAWING = {
    "─": "-",
    "━": "-",
    "│": "|",
    "┃": "|",
    "├": "+",
    "┤": "+",
    "┬": "+",
    "┴": "+",
    "┼": "+",
    "┌": "+",
    "┐": "+",
    "└": "+",
    "┘": "+",
    "╔": "+",
    "╗": "+",
    "╚": "+",
    "╝": "+",
    "║": "|",
    "═": "=",
    "╠": "+",
    "╣": "+",
    "╦": "+",
    "╩": "+",
    "╬": "+",
    "►": ">",
    "◄": "<",
    "▼": "v",
    "▲": "^",
    "↓": "v",
    "↑": "^",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "✅": "[OK]",
}


def convert_box_drawing(text: str) -> str:
  for unicode_char, ascii_char in _BOX_DRAWING.items():
      text = text.replace(unicode_char, ascii_char)
  return text


def simplify_math(text: str) -> str:
  """Replace lightweight LaTeX markers with readable text for PDF rendering."""
  replacements = [
      (r"\\\(", ""),
      (r"\\\)", ""),
      (r"\\\[", ""),
      (r"\\\]", ""),
      (r"\\mathcal\{S\}", "S"),
      (r"\\mathcal\{U\}", "U"),
      (r"\\mathcal\{E\}", "E"),
      (r"\\text\{PENDING\}", "PENDING"),
      (r"\\text\{UPLOADED\}", "UPLOADED"),
      (r"\\text\{PROCESSING\}", "PROCESSING"),
      (r"\\text\{COMPLETED\}", "COMPLETED"),
      (r"\\text\{FAILED\}", "FAILED"),
      (r"\\in", "∈"),
      (r"\\notin", "∉"),
      (r"\\geq", "≥"),
      (r"\\leq", "≤"),
      (r"\\approx", "≈"),
      (r"\\cdot", "·"),
      (r"\\emptyset", "∅"),
      (r"\\min", "min"),
      (r"\\mid", "|"),
      (r"\\rightarrow", "→"),
      (r"\\leftrightarrow", "↔"),
      (r"∎", "QED"),
  ]
  for pattern, repl in replacements:
      text = re.sub(pattern, repl, text)
  text = re.sub(r"\{([^}]+)\}", r"\1", text)
  return text


def md_to_html(md_text: str) -> str:
  md_text = simplify_math(md_text)
  md_text = convert_box_drawing(md_text)
  body = markdown.markdown(
      md_text,
      extensions=["tables", "fenced_code", "toc", "sane_lists"],
  )
  return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>VideoFlow — Rapport</title>
  <style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def html_to_pdf(html: str, output_path: Path) -> None:
  with output_path.open("wb") as pdf_file:
      status = pisa.CreatePDF(
          html,
          dest=pdf_file,
          encoding="utf-8",
          path=str(ROOT) + "/",
      )
  if status.err:
      raise RuntimeError(f"PDF generation failed with {status.err} error(s)")


def main() -> None:
  md_text = MD_PATH.read_text(encoding="utf-8")
  html = md_to_html(md_text)
  html_to_pdf(html, PDF_PATH)
  print(f"PDF generated: {PDF_PATH}")


if __name__ == "__main__":
  main()
