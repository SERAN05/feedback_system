import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable, PageBreak, Image, Table as PlatypusTable
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from src.common.extensions import db
from src.common.models import Staff, Course, Event, Question, FeedbackResponse, QuestionResponse, Student

# Matplotlib for advanced chart
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-GUI backend
    import matplotlib.pyplot as plt
    import numpy as np
    _MATPLOTLIB_AVAILABLE = True
except Exception:
    _MATPLOTLIB_AVAILABLE = False


def _institution_header(elements, styles, subtitle_line):
    snr_path = os.path.join(os.getcwd(), 'static', 'images', 'snr.png')
    logo_path = os.path.join(os.getcwd(), 'static', 'images', 'logo.png')
    snr_img = Image(snr_path, width=50, height=50) if os.path.exists(snr_path) else Paragraph('SNR', styles['Normal'])
    logo_img = Image(logo_path, width=50, height=50) if os.path.exists(logo_path) else Paragraph('LOGO', styles['Normal'])
    college_title = (
        "<para align='center' leading='12'>"
        "<font size=22 color='#0B6B4F'><b>SRI RAMAKRISHNA</b></font><br/>"
        "<font size=14 color='#0B6B4F'><b>ENGINEERING COLLEGE</b></font>"
        "</para>"
    )
    tbl = PlatypusTable([[snr_img, Paragraph(college_title, styles['Normal']), logo_img]], colWidths=[72, 420, 72])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.01 * inch))

    address_block = (
        "<para align='center' leading='8'>"
        "<font size=8>[Educational Service : SNR Sons Charitable Trust]</font><br/>"
        "<font size=8>Vattamalaipalayam, N.G.G.O. Colony Post,</font><br/>"
        "<font size=8>Coimbatore – 641022.</font>"
        "</para>"
    )
    elements.append(Paragraph(address_block, styles['Normal']))
    elements.append(Spacer(1, 0.01 * inch))
    elements.append(Paragraph(f"<para align='center'><font size=8><b>{subtitle_line}</b></font></para>", styles['Normal']))
    elements.append(Spacer(1, 0.06 * inch))


def generate_summary_pdf(category, summary):
    """Generate AI summary PDF with institutional header."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']

    _institution_header(elements, styles, "AI FEEDBACK SUMMARY")
    elements.append(Paragraph("AI Feedback Summary", title_style))
    elements.append(Spacer(1, 0.25 * inch))
    elements.append(Paragraph(f"Category: {category}", subtitle_style))
    elements.append(Spacer(1, 0.25 * inch))

    positive, negative, suggestions = extract_feedback_sections(summary)

    elements.append(Paragraph("Positive Feedback Summary", subtitle_style))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(positive or "No positive feedback detected.", normal_style))
    elements.append(Spacer(1, 0.25 * inch))

    elements.append(Paragraph("Negative Feedback Summary", subtitle_style))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(negative or "No negative feedback detected.", normal_style))
    elements.append(Spacer(1, 0.25 * inch))

    elements.append(Paragraph("Suggestions", subtitle_style))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(suggestions or "No suggestions detected.", normal_style))
    elements.append(Spacer(1, 0.25 * inch))
    doc.build(elements)
    buffer.seek(0)
    return buffer


def extract_feedback_sections(summary):
    """
    Extract positive, negative, and suggestions from the AI summary text.
    This is a simple heuristic based on keywords and sentence splitting.
    """
    import re
    positive = []
    negative = []
    suggestions = []
    positive_kw = [
        'good', 'great', 'excellent', 'appreciate', 'appreciated', 'well', 'positive', 'improved', 'improvement', 'liked',
        'enjoy', 'enjoyed', 'satisfactory', 'best', 'helpful', 'supportive', 'clean', 'neat', 'fast', 'friendly', 'effective',
        'clear', 'clarity', 'organized', 'efficient', 'engaging', 'useful', 'valuable', 'strong'
    ]
    negative_kw = [
        'concern', 'issue', 'problem', 'lack', 'insufficient', 'overpriced', 'small', 'persist', 'bad', 'poor', 'negative',
        'complain', 'complaint', 'criticize', 'limited', 'long waiting', 'not satisfied', 'slow', 'dirty', 'confusing',
        'late', 'delay', 'delayed', 'missing', 'unavailable', 'difficult', 'hard', 'inadequate'
    ]
    suggestion_kw = [
        'improve', 'consider', 'suggest', 'recommend', 'address', 'implement', 'review', 'adjust', 'should', 'could', 'need',
        'needs', 'required', 'must', 'better', 'add', 'increase', 'decrease', 'reduce', 'enhance', 'provide', 'ensure'
    ]
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', summary.strip()) if s]
    scored_positive_candidates = []
    for sent in sentences:
        s_lower = sent.lower()
        is_suggestion = any(k in s_lower for k in suggestion_kw)
        is_negative = any(k in s_lower for k in negative_kw)
        is_positive = any(k in s_lower for k in positive_kw) and not is_negative
        if is_suggestion:
            suggestions.append(sent)
        if is_negative:
            negative.append(sent)
        if is_positive:
            positive.append(sent)
        score = sum(s_lower.count(k) for k in positive_kw) - sum(s_lower.count(k) for k in negative_kw)
        if score > 0:
            scored_positive_candidates.append((score, sent))
    if not positive and scored_positive_candidates:
        scored_positive_candidates.sort(reverse=True, key=lambda x: x[0])
        positive = [sp[1] for sp in scored_positive_candidates[:2]]
    return (" ".join(positive).strip(), " ".join(negative).strip(), " ".join(suggestions).strip())


def generate_questions_pdf(staff_id, event_id):
    """Generate a PDF that lists only the questions for a staff/event."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']

    staff = Staff.query.get_or_404(staff_id)
    event = Event.query.get_or_404(event_id)
    course = Course.query.get_or_404(staff.course_id)

    _institution_header(elements, styles, "QUESTION LIST")
    elements.append(Paragraph("Questions", title_style))
    elements.append(Paragraph(f"Event: {event.title}", normal_style))
    elements.append(Paragraph(f"Course: {course.code} - {course.name}", normal_style))
    elements.append(Paragraph(f"Staff: {staff.name}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    feedback_responses = FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all()
    used_question_ids = set()
    for fr in feedback_responses:
        for qr in fr.question_responses:
            used_question_ids.add(qr.question_id)
    if used_question_ids:
        questions = Question.query.filter(Question.id.in_(used_question_ids)).order_by(Question.id).all()
    else:
        questions = Question.query.filter_by(is_archived=False).order_by(Question.id).all()

    table_data = [["Q.No", "Question"]]
    for idx, q in enumerate(questions, start=1):
        table_data.append([f"Q{idx}", q.text])

    table = Table(table_data, colWidths=[0.9 * inch, 5.9 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_excel_grouped_bar_chart(question_labels, question_texts, totals, c4, c3, c2, c1, pct_34, width_in=7.2, height_in=1.8, dpi=220):
    """Generate an Excel-style grouped bar chart as a high-resolution PNG (BytesIO)."""
    if not _MATPLOTLIB_AVAILABLE:
        return None

    labels = question_labels or []
    n = len(labels)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=(width_in, height_in))

    colors_excel = {
        "total": "#4472C4",
        "r4": "#70AD47",
        "r3": "#FFC000",
        "r2": "#A5A5A5",
        "r1": "#ED7D31",
    }

    bar_width = 0.12
    offsets = np.array([-2, -1, 0, 1, 2]) * bar_width

    ax.bar(x + offsets[0], totals, bar_width, label='Total number of students', color=colors_excel["total"])
    ax.bar(x + offsets[1], c4, bar_width, label='Rating 4', color=colors_excel["r4"])
    ax.bar(x + offsets[2], c3, bar_width, label='Rating 3', color=colors_excel["r3"])
    ax.bar(x + offsets[3], c2, bar_width, label='Rating 2', color=colors_excel["r2"])
    ax.bar(x + offsets[4], c1, bar_width, label='Rating 1', color=colors_excel["r1"])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel('Number of Students', fontsize=8)

    max_vals = [max(vals) if vals else 0 for vals in zip(totals, c4, c3, c2, c1)]
    y_max = max(max_vals + [1])
    ax.set_ylim(0, y_max * 1.25)

    for i, p in enumerate(pct_34):
        ax.text(x[i], max_vals[i] + (y_max * 0.04), f"{p:.1f}%", ha='center', va='bottom', fontsize=6)

    # Print each question text under its corresponding bar label in vertical form.
    if question_texts:
        for i, txt in enumerate(question_texts):
            short_txt = (txt[:34] + '...') if len(txt) > 37 else txt
            ax.text(
                x[i],
                -0.25,
                short_txt,
                rotation=90,
                ha='center',
                va='top',
                fontsize=4.5,
                transform=ax.get_xaxis_transform(),
                clip_on=False
            )

    # Place legend below the chart (centered) so series labels appear under the x-axis
    ax.legend(fontsize=6, ncol=5, loc='upper center', bbox_to_anchor=(0.5, -0.32), frameon=False)
    ax.grid(axis='y', linestyle='--', linewidth=0.4, alpha=0.5)
    ax.tick_params(axis='y', labelsize=7)

    # Reserve space at the bottom for the legend so it does not overlap the chart
    fig.subplots_adjust(left=0.05, right=0.995, top=0.92, bottom=0.50)
    fig.tight_layout()
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer


def generate_pdf_report(staff_id, event_id):
    """Generate a PDF report for a specific staff and event. Returns a BytesIO PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=22, leftMargin=22,
                            topMargin=18, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']

    staff = Staff.query.get_or_404(staff_id)
    event = Event.query.get_or_404(event_id)
    course = Course.query.get_or_404(staff.course_id)

    _institution_header(elements, styles, "STUDENTS’ CONSOLIDATED FEEDBACK ON FACULTY & CORRECTIVE MEASURES")

    current_year = datetime.utcnow().year
    academic_year = f"{current_year}-{current_year+1}"
    semester_label = "EVEN SEMESTER"
    class_name = "CLASS"

    meta_table_data = [
        [Paragraph(f"<b>ACADEMIC YEAR:</b> {academic_year}", normal_style), '',
         Paragraph(f"<b>SEMESTER:</b> {semester_label}", normal_style), ''],
        [Paragraph(f"<b>Name of the Faculty</b><br/>{staff.name}", normal_style),
         Paragraph(f"<b>Course Code & Name</b><br/>{course.code}<br/>{course.name}", normal_style),
         Paragraph(f"<b>Class</b><br/>{class_name}", normal_style),
         Paragraph(f"<b>No. of students offered the feedback</b><br/>{len(FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all())}", normal_style)]
    ]
    meta_tbl = Table(meta_table_data, colWidths=[2.5 * inch, 2.5 * inch, 1.2 * inch, 1.35 * inch])
    meta_tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('BACKGROUND', (0, 1), (-1, 1), colors.beige),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 0.08 * inch))

    feedback_responses = FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all()
    used_question_ids = set()
    for fr in feedback_responses:
        for qr in fr.question_responses:
            used_question_ids.add(qr.question_id)
    if used_question_ids:
        questions = Question.query.filter(Question.id.in_(used_question_ids)).order_by(Question.id).all()
    else:
        questions = []

    rating_counts = {q.id: {1: 0, 2: 0, 3: 0, 4: 0} for q in questions}
    for fr in feedback_responses:
        for qr in fr.question_responses:
            if qr.question_id in rating_counts:
                rating_counts[qr.question_id][qr.rating] += 1

    header_row = ['Parameter'] + [f"Q{i+1}" for i, _ in enumerate(questions)]

    measures_data = [header_row]
    for rating in [4, 3, 2, 1]:
        row = [str(rating)]
        for q in questions:
            row.append(str(rating_counts[q.id][rating]))
        measures_data.append(row)

    percent_row = ['% in 3 & 4']
    for q in questions:
        total = sum(rating_counts[q.id].values())
        pct = ((rating_counts[q.id][3] + rating_counts[q.id][4]) / total * 100) if total else 0
        percent_row.append(f"{pct:.1f}")
    measures_data.append(percent_row)

    table_total_width = doc.width
    first_col_width = 1.25 * inch
    dynamic_col_width = max(0.22 * inch, (table_total_width - first_col_width) / max(1, len(questions)))
    col_widths = [first_col_width] + [dynamic_col_width for _ in questions]
    measures_tbl = Table(measures_data, colWidths=col_widths)
    measures_tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    elements.append(measures_tbl)
    elements.append(Spacer(1, 0.06 * inch))

    if _MATPLOTLIB_AVAILABLE and questions:
        try:
            q_labels = [f"Q{i+1}" for i in range(len(questions))]
            q_texts = [q.text for q in questions]
            totals = [sum(rating_counts[q.id].values()) for q in questions]
            c1 = [rating_counts[q.id][1] for q in questions]
            c2 = [rating_counts[q.id][2] for q in questions]
            c3 = [rating_counts[q.id][3] for q in questions]
            c4 = [rating_counts[q.id][4] for q in questions]
            pct = [(c3[i] + c4[i]) / totals[i] * 100 if totals[i] else 0 for i in range(len(questions))]

            img_buffer = generate_excel_grouped_bar_chart(
                q_labels,
                q_texts,
                totals,
                c4,
                c3,
                c2,
                c1,
                pct,
                width_in=7.35,
                height_in=1.8,
                dpi=220,
            )

            if img_buffer is None:
                raise RuntimeError("Matplotlib not available")

            chart_img = Image(img_buffer, width=7.35 * inch, height=2.3 * inch)
            elements.append(chart_img)
            elements.append(Spacer(1, 0.05 * inch))
        except Exception as e:
            elements.append(Paragraph(f"Chart generation error: {e}", normal_style))
            elements.append(Spacer(1, 0.05 * inch))
    else:
        if not _MATPLOTLIB_AVAILABLE:
            elements.append(Paragraph("Matplotlib not installed; chart skipped. Add 'matplotlib' to requirements.txt to enable.", normal_style))
            elements.append(Spacer(1, 0.05 * inch))

    elements.append(Spacer(1, 0.02 * inch))

    elements.append(Paragraph("<font size=8><b>Kind Note:</b></font>", normal_style))
    elements.append(Paragraph("<font size=8>(i) A target of 75% from the maximum score is being considered for evaluation and <b>attained target of 75%</b> is to be checked for every parameter.</font>", normal_style))
    elements.append(Paragraph("<para align='center'><font size=8><b>(OR)</b></font></para>", normal_style))
    elements.append(Paragraph("<font size=8>(ii) Corrective measures shall be given for <b>One least score</b> in specified criteria.</font>", normal_style))
    elements.append(Spacer(1, 0.03 * inch))
    elements.append(Paragraph("<font size=8><b>Measures planned for improvement</b></font>", normal_style))

    class SignatureLines(Flowable):
        def __init__(self, total_width, left_label, right_label, line_length=170):
            super().__init__()
            self.width = total_width
            self.height = 40
            self.left_label = left_label
            self.right_label = right_label
            self.line_length = line_length

        def draw(self):
            c = self.canv
            y = 28
            c.setLineWidth(0.8)
            c.setDash(4, 3)
            c.line(0, y, self.line_length, y)
            c.line(self.width - self.line_length, y, self.width, y)
            c.setDash()
            c.setFont('Helvetica-Bold', 8)
            c.drawString(0, y - 14, self.left_label)
            c.drawRightString(self.width, y - 14, self.right_label)

    elements.append(Spacer(1, 0.15 * inch))
    elements.append(SignatureLines(doc.width, 'Signature of the Faculty', 'HOD'))

    doc.build(elements)
    buffer.seek(0)
    return buffer
