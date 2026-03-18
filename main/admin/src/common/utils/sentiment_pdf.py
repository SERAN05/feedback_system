import io
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Table as PlatypusTable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import inch
from src.common.utils.sentiment import batch_analyze

def _institution_header(elements, styles, subtitle_line):
    snr_path = os.path.join(os.getcwd(), 'static', 'images', 'snr.png')
    logo_path = os.path.join(os.getcwd(), 'static', 'images', 'logo.png')
    snr_img = Image(logo_path, width=80, height=80) if os.path.exists(logo_path) else Paragraph('SNR', styles['Normal'])
    logo_img = Image(snr_path, width=80, height=80) if os.path.exists(snr_path) else Paragraph('LOGO', styles['Normal'])
    header_html = ("<para align='center'><b>SRI RAMAKRISHNA ENGINEERING COLLEGE</b><br/>"
                   "<font size=9>[Educational Service: SNR Sons Charitable Trust]<br/>"
                   "[Autonomous Institution, Reaccredited by NAAC with 'A+' Grade]<br/>"
                   "[Approved by AICTE and Permanently Affiliated to Anna University, Chennai]<br/>"
                   "[ISO 9001:2015 Certified and all eligible programmes Accredited by NBA]<br/>"
                   "VATTAMALAI PALAYAM, N.G.G.O. COLONY POST, COIMBATORE – 641 022.<br/><br/><b>" + subtitle_line + "</b></font></para>")
    tbl = PlatypusTable([[snr_img, Paragraph(header_html, styles['Normal']), logo_img]], colWidths=[90, 380, 90])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.2*inch))

def generate_sentiment_pdf(feedbacks, category=None):
    """
    feedbacks: list of feedback strings
    category: optional string
    Returns: BytesIO PDF
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']

    _institution_header(elements, styles, "SENTIMENT ANALYSIS REPORT")
    elements.append(Paragraph("Sentiment Analysis Report", title_style))
    if category:
        elements.append(Paragraph(f"Category: {category}", subtitle_style))
    elements.append(Spacer(1, 0.25*inch))

    # Sentiment analysis
    results = batch_analyze(feedbacks)
    elements.append(Paragraph("Feedback Sentiment Table", subtitle_style))
    table_data = [["Feedback", "Sentiment", "Confidence"]]
    for r in results:
        table_data.append([r["text"], r["label"], str(r["score"])])
    table = Table(table_data, colWidths=[3.5*inch, 1.2*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # Sentiment counts for charts
    sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
    for r in results:
        sentiment_counts[r["label"]] += 1
    total = sum(sentiment_counts.values())
    pie_data = [sentiment_counts["Positive"], sentiment_counts["Neutral"], sentiment_counts["Negative"]]
    pie_labels = [f"Positive ({pie_data[0]})", f"Neutral ({pie_data[1]})", f"Negative ({pie_data[2]})"]

    # Pie chart
    elements.append(Paragraph("Sentiment Distribution (Pie Chart)", subtitle_style))
    drawing = Drawing(300, 200)
    pie = Pie()
    pie.x = 65
    pie.y = 15
    pie.width = 170
    pie.height = 170
    pie.data = pie_data
    pie.labels = pie_labels
    pie.slices.strokeWidth = 0.5
    pie.slices[0].fillColor = colors.green
    pie.slices[1].fillColor = colors.yellow
    pie.slices[2].fillColor = colors.red
    drawing.add(pie)
    elements.append(drawing)
    elements.append(Spacer(1, 0.3*inch))

    # Bar chart
    elements.append(Paragraph("Sentiment Distribution (Bar Chart)", subtitle_style))
    drawing2 = Drawing(400, 200)
    bar = VerticalBarChart()
    bar.x = 50
    bar.y = 30
    bar.height = 120
    bar.width = 300
    bar.data = [[sentiment_counts["Positive"], sentiment_counts["Neutral"], sentiment_counts["Negative"]]]
    bar.categoryAxis.categoryNames = ["Positive", "Neutral", "Negative"]
    bar.valueAxis.valueMin = 0
    bar.valueAxis.valueMax = max(pie_data) + 1
    bar.valueAxis.valueStep = 1
    bar.bars[0].fillColor = colors.green
    bar.bars[1].fillColor = colors.yellow
    bar.bars[2].fillColor = colors.red
    drawing2.add(bar)
    elements.append(drawing2)
    elements.append(Spacer(1, 0.3*inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer
