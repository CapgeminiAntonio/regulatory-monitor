"""Render a one-item regulatory impact report as a PDF (fpdf2, pure Python)."""

import logging
from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.models import Analysis, Impact, Policy, RegItem

# fontTools warns about font tables it can't subset (harmless with Segoe UI); keep the logs clean.
logging.getLogger("fontTools.subset").setLevel(logging.ERROR)

# Unicode TrueType fonts (regulatory text is full of “ ” § – …). First match wins.
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

NAVY = (23, 37, 84)
SLATE = (71, 85, 105)
LIGHT = (241, 245, 249)
IMPACT_COLORS = {"high": ((220, 38, 38), (255, 255, 255)), "medium": ((253, 186, 116), (67, 20, 7)),
                 "low": ((254, 243, 199), (146, 64, 14)), "none": ((241, 245, 249), (100, 116, 139))}
SEVERITY_COLORS = {"critical": (220, 38, 38), "high": (234, 88, 12), "medium": (217, 119, 6), "low": (100, 116, 139)}

# Fallback when no Unicode font is found: core fonts are Latin-1 only.
ASCII_MAP = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "•": "-",
                           "≥": ">=", "≤": "<=", "→": "->", "\u00a0": " "})


class ReportPDF(FPDF):
    def __init__(self, footer_note: str):
        super().__init__(format="Letter")
        self.footer_note = footer_note
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=20)
        self.font_family_name = "Helvetica"
        self.unicode = False
        for regular, bold in FONT_CANDIDATES:
            if Path(regular).exists() and Path(bold).exists():
                self.add_font("Body", "", regular)
                self.add_font("Body", "B", bold)
                self.font_family_name, self.unicode = "Body", True
                break

    def t(self, text: str | None) -> str:
        text = text or ""
        return text if self.unicode else text.translate(ASCII_MAP).encode("latin-1", "replace").decode("latin-1")

    def font(self, size: float, bold: bool = False, color=(15, 23, 42)):
        self.set_font(self.font_family_name, "B" if bold else "", size)
        self.set_text_color(*color)

    def footer(self):
        self.set_y(-14)
        self.font(7.5, color=(148, 163, 184))
        self.cell(0, 5, self.t(self.footer_note), align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="R")

    # building blocks ---------------------------------------------------------
    def section(self, title: str):
        self.ln(3)
        self.font(10, bold=True, color=NAVY)
        self.cell(0, 6, self.t(title.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(203, 213, 225)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def para(self, text: str, size: float = 10, color=(30, 41, 59)):
        self.font(size, color=color)
        self.multi_cell(0, size * 0.52, self.t(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullets(self, items: list[str], empty: str):
        if not items:
            self.para(empty, color=SLATE)
            return
        for item in items:
            self.font(10, color=(30, 41, 59))
            self.cell(5, 5.2, self.t("•"))
            self.multi_cell(0, 5.2, self.t(item), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(0.8)

    def pill(self, text: str, fill, fg, size: float = 8):
        self.font(size, bold=True, color=fg)
        self.set_fill_color(*fill)
        w = self.get_string_width(self.t(text)) + 5
        self.cell(w, 5.5, self.t(text), fill=True, align="C")
        return w

    def meta_row(self, label: str, value: str, link: str | None = None):
        self.font(9, bold=True, color=SLATE)
        self.cell(38, 5.5, self.t(label))
        self.font(9, color=(15, 23, 42) if not link else (29, 78, 216))
        self.multi_cell(0, 5.5, self.t(value), link=link or "", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def policy_card(pdf: ReportPDF, imp: Impact, policy: Policy | None) -> None:
    top = pdf.get_y()
    fill, fg = IMPACT_COLORS[imp.impact]
    pdf.set_x(pdf.l_margin + 4)
    pdf.font(11, bold=True)
    pdf.cell(pdf.w - pdf.l_margin - pdf.r_margin - 34, 6, pdf.t(policy.title if policy else imp.policy_id))
    pdf.pill(f"{imp.impact.upper()} IMPACT", fill, fg)
    pdf.ln(7)
    indent = pdf.l_margin + 4

    def line(label: str, value: str, highlight: bool = False):
        pdf.set_x(indent)
        pdf.font(9, bold=True, color=SLATE)
        pdf.cell(24, 5, pdf.t(label))
        pdf.font(9.5, color=(30, 58, 138) if highlight else (30, 41, 59))
        pdf.multi_cell(0, 5, pdf.t(value), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(0.6)

    if policy and policy.owner:
        line("Owner", policy.owner)
    if imp.affected_sections:
        line("Sections", ", ".join("§" + s.lstrip("§") for s in imp.affected_sections))
    line("Why", imp.rationale)
    line("Action", imp.recommended_action, highlight=True)
    line("Confidence", f"{imp.confidence:.0%}")
    pdf.set_fill_color(*fill)
    pdf.rect(pdf.l_margin, top, 1.6, pdf.get_y() - top - 1, style="F")  # colored accent bar
    pdf.ln(3)


def build_report_pdf(
    item: RegItem, analysis: Analysis, impacts: list[Impact], policies: dict[str, Policy], client_name: str
) -> bytes:
    pdf = ReportPDF(footer_note=f"AI-generated by Regulatory Change Monitor ({analysis.model}). Verify against the source before acting.")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Header band
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_xy(pdf.l_margin, 7)
    pdf.font(9, color=(191, 219, 254))
    pdf.cell(0, 5, pdf.t(f"REGULATORY IMPACT REPORT  ·  {client_name}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.font(8.5, color=(191, 219, 254))
    pdf.cell(0, 5, pdf.t(f"Prepared {date.today():%B %d, %Y}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(32)

    # Title + badges
    pdf.font(16, bold=True, color=(15, 23, 42))
    pdf.multi_cell(0, 7.5, pdf.t(analysis.title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1.5)
    pdf.pill(analysis.regulation.replace("_", " "), LIGHT, NAVY)
    pdf.cell(2, 5.5)
    pdf.pill(f"{analysis.severity.upper()} SEVERITY", SEVERITY_COLORS.get(analysis.severity, SLATE), (255, 255, 255))
    pdf.ln(8)

    # Metadata
    pdf.meta_row("Source", item.source)
    pdf.meta_row("Published", item.published.strftime("%B %d, %Y") if item.published else "Unknown")
    pdf.meta_row("Effective date", analysis.effective_date or "Not stated")
    pdf.meta_row("Comment deadline", analysis.comment_deadline or "n/a")
    pdf.meta_row("Source document", item.url, link=item.url)

    pdf.section("Summary")
    pdf.para(analysis.summary)
    pdf.section("What changed")
    pdf.bullets(analysis.what_changed, "No specific changes identified.")
    pdf.section("New obligations")
    pdf.bullets(analysis.new_obligations, "No new obligations identified.")
    pdf.section("Who is affected")
    pdf.para(analysis.who_is_affected.strip().strip('"“”'))

    # Policy impacts
    hits = [i for i in impacts if i.impact != "none"]
    pdf.section(f"Affected client policies ({len(hits)} of {len(impacts)})")
    if not hits:
        pdf.para("No client policies require changes for this update.", color=SLATE)
    for imp in hits:
        policy = policies.get(imp.policy_id)
        # Dry-run the card; if it would cross a page boundary, start it on a fresh page.
        with pdf.offset_rendering() as dummy:
            policy_card(dummy, imp, policy)
        if dummy.page_break_triggered:
            pdf.add_page()
        policy_card(pdf, imp, policy)

    unaffected = [policies[i.policy_id].title for i in impacts if i.impact == "none" and i.policy_id in policies]
    if unaffected:
        pdf.ln(1)
        pdf.para("Reviewed, no change needed: " + "; ".join(sorted(unaffected)) + ".", size=8.5, color=SLATE)

    return bytes(pdf.output())
