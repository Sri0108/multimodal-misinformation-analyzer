from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


def _format_explanations(explanation):
    if isinstance(explanation, list):
        return "<br/>".join(f"- {escape(str(item))}" for item in explanation)
    return escape(str(explanation))


def _format_signals(signals):
    rows = [['Signal', 'Value']]

    for key, value in signals.items():
        label = key.replace('_', ' ').title()
        rows.append([label, str(value)])

    return rows


def _format_sources(sources):
    rows = [['Source', 'Why Check It']]

    for item in sources:
        rows.append([item.get('source', ''), item.get('title', '')])

    return rows

def generate_pdf_report(result, input_id):
    report_filename = f"report_{input_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    workspace_root = Path(__file__).resolve().parent.parent
    report_dir = workspace_root / 'reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = str((report_dir / report_filename).resolve())
    
    doc = SimpleDocTemplate(report_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("<b>Multimodal Misinformation Analysis Report</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    date_text = Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
    story.append(date_text)
    story.append(Spacer(1, 12))
    
    data = [
        ['Metric', 'Value'],
        ['Prediction', result['prediction']],
        ['Confidence Score', f"{result['confidence']:.2%}"],
        ['Manipulation Score', f"{result['manipulation_score']:.2f}"],
        ['Sentiment', result['sentiment']]
    ]
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    story.append(Spacer(1, 12))
    
    explanation = Paragraph(
        f"<b>Explanation:</b><br/>{_format_explanations(result.get('explanation', []))}",
        styles['Normal']
    )
    story.append(explanation)

    if result.get('reason_summary'):
        story.append(Spacer(1, 12))
        reasons = Paragraph(
            f"<b>Reason Summary:</b><br/>{_format_explanations(result.get('reason_summary', []))}",
            styles['Normal']
        )
        story.append(reasons)

    if result.get('signals'):
        story.append(Spacer(1, 12))
        signals_table = Table(_format_signals(result['signals']))
        signals_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(signals_table)

    if result.get('trusted_sources'):
        story.append(Spacer(1, 12))
        sources_table = Table(_format_sources(result['trusted_sources']))
        sources_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(sources_table)
    
    if result.get('extracted_text'):
        story.append(Spacer(1, 12))
        extracted = Paragraph(
            f"<b>Extracted Text:</b><br/>{escape(result['extracted_text'][:500])}",
            styles['Normal']
        )
        story.append(extracted)
    
    doc.build(story)
    return report_path
