"""Generate PDF and wiring SVG from the beginner guide (requires reportlab)."""
from html import escape
from pathlib import Path
import re
from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT = DOCS / "Guia_montaje_catapulta_ESP32.pdf"
INK = colors.HexColor("#20343C")
TEAL = colors.HexColor("#087F82")
LIGHT = colors.HexColor("#EDF5F5")
MUTED = colors.HexColor("#536971")
WIDTH = A4[0] - 84
TICK = chr(96)
STYLES = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10,
                           leading=14, textColor=INK, spaceAfter=9),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22,
                         leading=27, textColor=TEAL, spaceAfter=17, keepWithNext=True),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12,
                         leading=16, textColor=TEAL, spaceBefore=8,
                         spaceAfter=8, keepWithNext=True),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=9,
                           leading=12, textColor=INK),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=9,
                           leading=12, textColor=INK, backColor=LIGHT,
                           borderPadding=9, spaceBefore=4, spaceAfter=14),
}


def inline(text):
    """Render the Markdown subset used in the guide, escaping literal text."""
    pattern = "(" + TICK + "[^" + TICK + "]+" + TICK + r"|\*\*.+?\*\*|\[[^\]]+\]\([^)]+\))"
    text = text.replace("\u2192", " > ")
    pieces = []
    for piece in re.split(pattern, text):
        if piece.startswith(TICK) and piece.endswith(TICK):
            pieces.append('<font name="Courier">' + escape(piece[1:-1]) + "</font>")
        elif piece.startswith("**") and piece.endswith("**"):
            pieces.append("<b>" + escape(piece[2:-2]) + "</b>")
        elif re.fullmatch(r"\[[^\]]+\]\([^)]+\)", piece):
            label, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", piece).groups()
            pieces.append('<a href="' + escape(url, quote=True) +
                          '" color="#087F82"><u>' + escape(label) + "</u></a>")
        else:
            pieces.append(escape(piece))
    return "".join(pieces)


def wiring():
    drawing = Drawing(WIDTH, 210)

    def label(x, y, text, bold=False, color=INK, size=10):
        drawing.add(String(x, y, text, fontName="Helvetica-Bold" if bold else "Helvetica",
                           fontSize=size, fillColor=color))

    def box(x, y, width, height):
        drawing.add(Rect(x, y, width, height, rx=7, ry=7,
                         fillColor=LIGHT, strokeColor=None))

    def wire(points, color):
        for start, end in zip(points, points[1:]):
            drawing.add(Line(*start, *end, strokeColor=color, strokeWidth=2))

    box(0, 92, 155, 100)
    label(12, 172, "ESP32", True)
    label(12, 151, "USB al ordenador")
    label(89, 127, "GPIO26", True)
    label(113, 106, "GND", True)
    box(365, 60, 146, 110)
    label(378, 149, "SERVO", True)
    label(378, 124, "Señal")
    label(378, 99, "V+ (5 V)")
    label(378, 74, "GND")
    box(0, 0, 155, 69)
    label(12, 48, "FUENTE EXTERNA", True)
    label(12, 28, "5 V regulados")
    label(137, 28, "+", True)
    label(137, 9, "-", True)
    orange = colors.HexColor("#B7650C")
    red = colors.HexColor("#C83D45")
    wire([(155, 130), (365, 130)], orange)
    label(213, 138, "Señal", color=orange, size=9)
    wire([(155, 32), (300, 32), (300, 104), (365, 104)], red)
    label(308, 112, "+5 V", color=red, size=9)
    wire([(155, 110), (197, 110), (197, 12)], INK)
    wire([(155, 12), (341, 12), (341, 79), (365, 79)], INK)
    drawing.add(Circle(197, 12, 3, fillColor=INK, strokeColor=None))
    label(217, 20, "GND común", True, size=9)
    return drawing


def table(lines):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    widths = [WIDTH * .35, WIDTH * .65] if len(rows[0]) == 2 else [WIDTH * .13, WIDTH * .32, WIDTH * .55]
    cells = [[Paragraph(("<b>" + inline(cell) + "</b>") if i == 0 else inline(cell),
                        STYLES["cell"]) for cell in row] for i, row in enumerate(rows)]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#DCE6E8")),
    ]))
    return result


def story_from_markdown(text):
    lines = text.splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line == "<!-- page -->":
            story.append(PageBreak())
        elif line.startswith(TICK * 3):
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith(TICK * 3):
                code.append(escape(lines[index]))
                index += 1
            story.append(Paragraph("<br/>".join(code), STYLES["code"]))
        elif line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), STYLES["h1"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), STYLES["h2"]))
        elif line.startswith("!["):
            story.extend([wiring(), Spacer(1, 12)])
        elif line.startswith("|"):
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            story.extend([table(block), Spacer(1, 12)])
            continue
        elif line.startswith("- "):
            story.append(Paragraph("• " + inline(line[2:]), STYLES["body"]))
        else:
            story.append(Paragraph(inline(line), STYLES["body"]))
        index += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D5E1E3"))
    canvas.line(42, 37, A4[0] - 42, 37)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(42, 23, "CATAPULTA · GUÍA DESDE CERO")
    canvas.drawRightString(A4[0] - 42, 23, str(doc.page))
    canvas.restoreState()


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    renderSVG.drawToFile(wiring(), str(DOCS / "conexion.svg"))
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=42,
                            leftMargin=42, topMargin=40, bottomMargin=49,
                            title="Catapulta ESP32: guía desde cero",
                            author="Proyecto catapulta",
                            subject="Instalación, cableado y primeros pasos")
    source = (DOCS / "GUIA_DESDE_CERO.md").read_text(encoding="utf-8")
    doc.build(story_from_markdown(source), onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
