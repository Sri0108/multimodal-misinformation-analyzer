from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


THEME = {
    "navy": colors.HexColor("#10264c"),
    "primary": colors.HexColor("#1f4fa3"),
    "primary_dark": colors.HexColor("#153b7f"),
    "accent": colors.HexColor("#0f766e"),
    "surface": colors.HexColor("#ffffff"),
    "surface_soft": colors.HexColor("#f7fbff"),
    "surface_tint": colors.HexColor("#eef4ff"),
    "border": colors.HexColor("#d9e4f5"),
    "text": colors.HexColor("#10213c"),
    "muted": colors.HexColor("#546179"),
    "success": colors.HexColor("#137a49"),
    "warning": colors.HexColor("#a46b07"),
    "danger": colors.HexColor("#b4232f"),
}


def _format_explanations(explanation):
    if isinstance(explanation, list):
        return "<br/>".join(f"- {escape(str(item))}" for item in explanation)
    return escape(str(explanation))


def _format_signals(signals):
    rows = [["Signal", "Value"]]

    for key, value in signals.items():
        label = key.replace("_", " ").title()
        rows.append([label, str(value)])

    return rows


def _format_sources(sources):
    rows = [["Source", "Why Check It"]]

    for item in sources:
        rows.append([item.get("source", ""), item.get("title", "")])

    return rows


def _verdict_tone(prediction):
    lowered = (prediction or "").lower()
    if "fake" in lowered:
        return THEME["danger"]
    if "real" in lowered:
        return THEME["success"]
    return THEME["warning"]


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="DashboardEyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#9ac2ff"),
            alignment=TA_LEFT,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DashboardTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DashboardLead",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#d4e3fa"),
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionEyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#355892"),
            alignment=TA_LEFT,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=THEME["navy"],
            alignment=TA_LEFT,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=THEME["muted"],
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetricValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=20,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetricLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#d7e7ff"),
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetricNote",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#b9cff0"),
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Pill",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
    )

    return styles


def _card_table(data, col_widths):
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), THEME["surface_tint"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), THEME["navy"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9.5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), THEME["surface"]),
                ("TEXTCOLOR", (0, 1), (-1, -1), THEME["muted"]),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("LEADING", (0, 1), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.75, THEME["border"]),
                ("BOX", (0, 0), (-1, -1), 0.75, THEME["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
            ]
        )
    )
    return table


def _section_header(eyebrow, title, styles):
    return [
        Paragraph(escape(eyebrow.upper()), styles["SectionEyebrow"]),
        Paragraph(escape(title), styles["SectionTitle"]),
    ]


def _metric_cards(result, styles):
    metrics = [
        [
            Paragraph(escape(result.get("prediction", "Uncertain")), styles["MetricValue"]),
            Paragraph("Primary Verdict", styles["MetricLabel"]),
            Paragraph("Final label after source verification and classifier fusion.", styles["MetricNote"]),
        ],
        [
            Paragraph(f"{result.get('confidence', 0.0):.0%}", styles["MetricValue"]),
            Paragraph("Confidence", styles["MetricLabel"]),
            Paragraph("Overall confidence for the current result.", styles["MetricNote"]),
        ],
        [
            Paragraph(str(result.get("source_evidence_count", 0)), styles["MetricValue"]),
            Paragraph("Trusted URLs Found", styles["MetricLabel"]),
            Paragraph("Supporting evidence sources attached to this report.", styles["MetricNote"]),
        ],
    ]

    card_colors = [THEME["primary_dark"], THEME["primary"], THEME["accent"]]
    table = Table(metrics, colWidths=[2.05 * inch, 2.05 * inch, 2.05 * inch], hAlign="LEFT")
    style_commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]

    for index, fill in enumerate(card_colors):
        style_commands.extend(
            [
                ("BACKGROUND", (index, 0), (index, 0), fill),
                ("BOX", (index, 0), (index, 0), 0.75, fill),
            ]
        )

    table.setStyle(TableStyle(style_commands))
    return table


def _hero_block(result, styles):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verification_mode = result.get("verification_mode", "classifier_fallback").replace("_", " ").title()
    title_block = Table(
        [
            [Paragraph("RESULT WORKSPACE", styles["DashboardEyebrow"])],
            [Paragraph("Multimodal Misinformation Analysis Report", styles["DashboardTitle"])],
            [
                Paragraph(
                    (
                        f"Generated {generated_at}. Verification mode: {escape(verification_mode)}. "
                        "This report follows the same evidence-first dashboard language used in the main application."
                    ),
                    styles["DashboardLead"],
                )
            ],
        ],
        colWidths=[6.45 * inch],
        hAlign="LEFT",
    )
    title_block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), THEME["navy"]),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#244f82")),
                ("LEFTPADDING", (0, 0), (-1, -1), 18),
                ("RIGHTPADDING", (0, 0), (-1, -1), 18),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )

    pill = Table(
        [[Paragraph(escape(result.get("prediction", "Uncertain")), styles["Pill"])]],
        colWidths=[1.65 * inch],
        hAlign="RIGHT",
    )
    pill.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _verdict_tone(result.get("prediction", ""))),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    hero = Table([[title_block, pill]], colWidths=[5.05 * inch, 1.4 * inch], hAlign="LEFT")
    hero.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return hero


def _rich_text_block(title_eyebrow, title, body_html, styles):
    block = []
    block.extend(_section_header(title_eyebrow, title, styles))
    body = Table([[Paragraph(body_html, styles["CardBody"])]], colWidths=[6.45 * inch], hAlign="LEFT")
    body.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), THEME["surface_soft"]),
                ("BOX", (0, 0), (-1, -1), 0.75, THEME["border"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    block.append(body)
    return block


def generate_pdf_report(result, input_id):
    report_filename = f"report_{input_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    workspace_root = Path(__file__).resolve().parent.parent
    report_dir = workspace_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = str((report_dir / report_filename).resolve())

    doc = SimpleDocTemplate(
        report_path,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    story = []
    styles = _build_styles()

    story.append(_hero_block(result, styles))
    story.append(Spacer(1, 14))
    story.append(_metric_cards(result, styles))
    story.append(Spacer(1, 16))

    metrics_data = [
        ["Metric", "Value"],
        ["Sentiment", result.get("sentiment", "neutral")],
        ["Manipulation Score", f"{result.get('manipulation_score', 0.0):.2f}"],
        ["Claim Category", result.get("claim_category", "general")],
        ["Verification Mode", result.get("verification_mode", "classifier_fallback").replace("_", " ").title()],
    ]
    story.extend(_section_header("Result Summary", "Core metrics", styles))
    story.append(_card_table(metrics_data, [2.65 * inch, 3.8 * inch]))

    explanation_html = _format_explanations(result.get("explanation", []))
    story.append(Spacer(1, 14))
    story.extend(_rich_text_block("Detailed Explanation", "Why the system reached this conclusion", explanation_html, styles))

    if result.get("reason_summary"):
        story.append(Spacer(1, 14))
        story.extend(
            _rich_text_block(
                "Source-backed Reasoning",
                "Reason summary",
                _format_explanations(result.get("reason_summary", [])),
                styles,
            )
        )

    if result.get("signals"):
        story.append(Spacer(1, 14))
        story.extend(_section_header("Signals", "Detection signals", styles))
        story.append(_card_table(_format_signals(result["signals"]), [3.2 * inch, 3.25 * inch]))

    if result.get("trusted_sources"):
        story.append(Spacer(1, 14))
        story.extend(_section_header("Trusted URLs", "Evidence sources", styles))
        story.append(_card_table(_format_sources(result["trusted_sources"]), [2.15 * inch, 4.3 * inch]))

    if result.get("extracted_text"):
        story.append(Spacer(1, 14))
        story.extend(
            _rich_text_block(
                "Source Snapshot",
                "Extracted text",
                escape(result["extracted_text"][:900]).replace("\n", "<br/>"),
                styles,
            )
        )

    doc.build(story)
    return report_path
