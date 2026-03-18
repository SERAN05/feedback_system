def generate_summary_pdf(category, summary):
    """
    Generate a PDF containing the AI summary for a category.
    Returns: BytesIO object containing the PDF.
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

    elements.append(Paragraph("AI Feedback Summary", title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph(f"Category: {category}", subtitle_style))
    elements.append(Spacer(1, 0.25*inch))

    # Split summary into improved sections
    positive, negative, actionable = extract_feedback_sections_v2(summary)

    elements.append(Paragraph("Positive Highlights (Strengths)", subtitle_style))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(positive or "No positive feedback detected.", normal_style))
    elements.append(Spacer(1, 0.25*inch))

    elements.append(Paragraph("Negative Highlights (Challenges/Weaknesses)", subtitle_style))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(negative or "No negative feedback detected.", normal_style))
    elements.append(Spacer(1, 0.25*inch))

    elements.append(Paragraph("Actionable Insights / Improvements", subtitle_style))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(Paragraph(actionable or "No actionable insights detected.", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    doc.build(elements)
    buffer.seek(0)
    return buffer

def extract_feedback_sections_v2(summary):
    """
    Improved extraction: Positive, Negative, Actionable Insights.
    Actionable Insights are suggestions tied to negative points only.
    """
    import re
    positive = []
    negative = []
    actionable = []
    sentences = re.split(r'(?<=[.!?])\s+', summary.strip())
    # Expanded keyword sets
    positive_keywords = [
        "good", "great", "excellent", "amazing", "appreciated", "well", "useful", "clean", "neat", "satisfied",
        "comfortable", "friendly", "supportive", "tasty", "fresh", "enjoyable", "nice", "fast", "affordable",
        "improved", "adequate", "pleasant", "happy", "commendable"
    ]
    negative_keywords = [
        "bad", "poor", "slow", "late", "dirty", "unhygienic", "crowded", "noisy", "expensive", "overpriced",
        "difficult", "uncomfortable", "unsatisfied", "insufficient", "lacking", "limited", "rusty",
        "problem", "issue", "weak", "broken", "inconvenient", "frustrating", "worst"
    ]
    improvement_keywords = [
        "should", "need", "must", "required", "request", "suggest", "improve", "increase", "decrease",
        "better", "change", "fix", "resolve", "upgrade", "maintain", "introduce", "add", "expand",
        "replace", "reduce", "ensure", "provide", "enhance"
    ]

    # Improved logic: extract segments for each section
    s = summary.lower()
    positive_section = ""
    negative_section = ""
    improvement_section = ""

    # Find positive segment
    for kw in ["appreciate", "praise", "good", "great", "excellent", "amazing", "improved", "well", "satisfied", "commendable", "pleasant", "happy", "supportive", "fresh", "tasty", "enjoyable", "friendly", "useful", "adequate", "comfortable", "affordable", "nice", "clean", "neat"]:
        idx = s.find(kw)
        if idx != -1:
            # Extract up to next period or end
            end_idx = s.find('.', idx)
            if end_idx == -1:
                end_idx = len(s)
            positive_section = summary[idx:end_idx+1].strip()
            break

    # Find negative segment
    for kw in ["concern", "issue", "problem", "bad", "poor", "slow", "late", "dirty", "unhygienic", "crowded", "noisy", "expensive", "overpriced", "difficult", "uncomfortable", "unsatisfied", "insufficient", "lacking", "limited", "rusty", "weak", "broken", "inconvenient", "frustrating", "worst", "arise", "persist"]:
        idx = s.find(kw)
        if idx != -1:
            end_idx = s.find('.', idx)
            if end_idx == -1:
                end_idx = len(s)
            negative_section = summary[idx:end_idx+1].strip()
            break

    # Find improvement/suggestion segment (to negative feedback)
    for kw in ["should", "need", "must", "required", "request", "suggest", "improve", "increase", "decrease", "better", "change", "fix", "resolve", "upgrade", "maintain", "introduce", "add", "expand", "replace", "reduce", "ensure", "provide", "enhance", "recommend", "consider", "address", "offer", "expand", "revise"]:
        idx = s.find(kw)
        if idx != -1:
            end_idx = s.find('.', idx)
            if end_idx == -1:
                end_idx = len(s)
            improvement_section = summary[idx:end_idx+1].strip()
            break

    # If quick segment extraction failed, attempt a sentence-level salvage for positives
    if not positive_section:
        # Look for any sentence containing positive keywords
        sentences = re.split(r'(?<=[.!?])\s+', summary.strip())
        for sent in sentences:
            if any(pk in sent.lower() for pk in positive_keywords):
                positive_section = sent.strip()
                break
    # Fallbacks if nothing found
    if not positive_section:
        positive_section = "(No explicit positive highlights extracted.)"
    if not negative_section:
        negative_section = "(No significant negative issues found.)"
    if not improvement_section:
        improvement_section = "(No actionable suggestions identified.)"

    return (positive_section, negative_section, improvement_section)
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import inch
from src.common.extensions import db
from src.common.models import Staff, Course, Event, Question, FeedbackResponse, QuestionResponse, Student

def generate_pdf_report(staff_id, event_id):
    """
    Generate a PDF report for a specific staff and event.
    Returns: BytesIO object containing the PDF.
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

    staff = Staff.query.get_or_404(staff_id)
    event = Event.query.get_or_404(event_id)
    course = Course.query.get_or_404(staff.course_id)

    elements.append(Paragraph("Feedback Report", title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph(f"Event: {event.title}", subtitle_style))
    elements.append(Paragraph(f"Course: {course.code} - {course.name}", subtitle_style))
    elements.append(Paragraph(f"Staff: {staff.name}", subtitle_style))
    elements.append(Spacer(1, 0.5*inch))

    feedback_responses = FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all()
    questions = Question.query.all()
    question_data = []
    for question in questions:
        ratings = []
        for feedback in feedback_responses:
            response = QuestionResponse.query.filter_by(feedback_id=feedback.id, question_id=question.id).first()
            if response:
                ratings.append(response.rating)
        if ratings:
            avg = sum(ratings) / len(ratings)
            question_data.append((question.text, round(avg, 2), len(ratings)))
        else:
            question_data.append((question.text, 0, 0))

    table_data = [['Question', 'Average Rating', 'Responses']]
    table_data.extend(question_data)
    table = Table(table_data, colWidths=[4*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))

    drawing = Drawing(500, 250)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 50
    bc.height = 150
    bc.width = 400
    bc.data = [[data[1] for data in question_data]]
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 4
    bc.valueAxis.valueStep = 1
    bc.categoryAxis.labels = [f"Q{i+1}" for i in range(len(question_data))]
    bc.barLabelFormat = '%.2f'
    drawing.add(bc)
    elements.append(drawing)
    elements.append(Spacer(1, 0.5*inch))

    responded_students = db.session.query(Student.id).join(FeedbackResponse, Student.id == FeedbackResponse.student_id)\
                         .filter(FeedbackResponse.staff_id == staff_id, FeedbackResponse.event_id == event_id)\
                         .distinct().count()
    total_students = Student.query.count()
    elements.append(Paragraph("Participation Statistics", subtitle_style))
    elements.append(Paragraph(f"Responses: {responded_students} students", normal_style))
    elements.append(Paragraph(f"Total Students: {total_students} students", normal_style))
    if total_students > 0:
        response_rate = (responded_students / total_students) * 100
        elements.append(Paragraph(f"Response Rate: {response_rate:.2f}%", normal_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer