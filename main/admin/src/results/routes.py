import io
import zipfile
from io import BytesIO

from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph

from src.common.extensions import db
from src.common.models import Event, Course, Staff, Question, Student, FeedbackResponse, QuestionResponse
from src.common.utils.pdf_generator import generate_pdf_report, generate_questions_pdf


def register_results_routes(admin_bp):
    @admin_bp.route('/results')
    @login_required
    def results():
        if not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.login'))

        event_id = request.args.get('event_id')

        if event_id:
            try:
                selected_event = Event.query.filter_by(id=int(event_id)).first()
                if not selected_event:
                    flash('Event not found', 'danger')
                    selected_event = None
            except Exception:
                selected_event = None
        else:
            try:
                selected_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
            except Exception:
                selected_event = Event.query.filter_by(is_active=True).first()

        courses = Course.query.all()
        staffs = Staff.query.all()
        questions = Question.query.filter_by(is_archived=False).all()
        students = Student.query.order_by(Student.roll_number).all()

        responded_ids = set()
        if selected_event:
            responded_ids = set([r[0] for r in db.session.query(FeedbackResponse.student_id).filter_by(event_id=selected_event.id).distinct().all()])

        events = Event.query.filter_by(is_deleted=False).order_by(Event.created_at.desc()).all()
        return render_template('domains/results/results.html', active_event=selected_event,
                               courses=courses, staffs=staffs, questions=questions,
                               students=students, responded_ids=responded_ids, events=events)

    @admin_bp.route('/api/results/staff/<int:staff_id>')
    @login_required
    def get_staff_results(staff_id):
        if not current_user.is_admin:
            return jsonify({'error': 'Access denied'}), 403

        staff = Staff.query.get_or_404(staff_id)
        event_id = request.args.get('event_id')
        if not event_id:
            try:
                active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
            except Exception:
                active_event = Event.query.filter_by(is_active=True).first()
            if active_event:
                event_id = active_event.id
            else:
                return jsonify({'error': 'No active event found'}), 404
        else:
            event_id = int(event_id)

        feedback_responses = FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all()

        question_averages = {}
        used_q_ids = set()
        for fb in feedback_responses:
            for qr in fb.question_responses:
                used_q_ids.add(qr.question_id)

        if used_q_ids:
            questions = Question.query.filter(Question.id.in_(used_q_ids)).order_by(Question.id).all()
        else:
            questions = []

        for q in questions:
            ratings = []
            for feedback in feedback_responses:
                resp = QuestionResponse.query.filter_by(feedback_id=feedback.id, question_id=q.id).first()
                if resp:
                    ratings.append(resp.rating)
            avg = sum(ratings) / len(ratings) if ratings else 0
            question_averages[q.id] = {
                'question_text': q.text,
                'average': round(avg, 2),
                'count': len(ratings)
            }

        responded_students = db.session.query(Student.id).join(FeedbackResponse, Student.id == FeedbackResponse.student_id)\
            .filter(FeedbackResponse.staff_id == staff_id, FeedbackResponse.event_id == event_id)\
            .distinct().count()
        total_students = Student.query.count()
        responded_student_ids = db.session.query(FeedbackResponse.student_id)\
            .filter_by(event_id=event_id, staff_id=staff_id).distinct().all()
        responded_ids = [rid[0] for rid in responded_student_ids]
        non_responder_students = Student.query.filter(~Student.id.in_(responded_ids)).all()
        non_responders = [{'roll_number': s.roll_number, 'name': s.name} for s in non_responder_students]

        return jsonify({
            'staff_name': staff.name,
            'course_name': staff.course.name,
            'question_averages': question_averages,
            'responded_count': responded_students,
            'total_students': total_students,
            'non_responders': non_responders,
            'response_percentage': round((responded_students / total_students * 100), 2) if total_students > 0 else 0
        })

    @admin_bp.route('/api/event/<int:event_id>/courses')
    @login_required
    def get_event_courses(event_id):
        if not current_user.is_admin:
            return jsonify({'error': 'Access denied'}), 403

        event = Event.query.get_or_404(event_id)
        courses_data = []
        for course in event.courses:
            staffs = [{'id': s.id, 'name': s.name} for s in course.staffs]
            courses_data.append({'id': course.id, 'code': course.code, 'name': course.name, 'staffs': staffs})

        return jsonify({'event_id': event.id, 'event_title': event.title, 'courses': courses_data})

    @admin_bp.route('/download_report/<int:staff_id>')
    @login_required
    def download_report(staff_id):
        if not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.login'))

        event_id = request.args.get('event_id')
        if not event_id:
            try:
                active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
            except Exception:
                active_event = Event.query.filter_by(is_active=True).first()
            if active_event:
                event_id = active_event.id
            else:
                flash('No active event found', 'danger')
                return redirect(url_for('admin.results'))
        else:
            event_id = int(event_id)

        pdf_buffer = generate_pdf_report(staff_id, event_id)
        staff = Staff.query.get_or_404(staff_id)
        event = Event.query.get_or_404(event_id)
        filename = f"report_{staff.course.code}_{staff.name.replace(' ', '_')}_{event.title.replace(' ', '_')}.pdf"
        return send_file(BytesIO(pdf_buffer.getvalue()), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)

    @admin_bp.route('/download_questions/<int:staff_id>')
    @login_required
    def download_questions(staff_id):
        if not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.login'))

        event_id = request.args.get('event_id')
        if not event_id:
            try:
                active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
            except Exception:
                active_event = Event.query.filter_by(is_active=True).first()
            if active_event:
                event_id = active_event.id
            else:
                flash('No active event found', 'danger')
                return redirect(url_for('admin.results'))
        else:
            event_id = int(event_id)

        pdf_buffer = generate_questions_pdf(staff_id, event_id)
        staff = Staff.query.get_or_404(staff_id)
        event = Event.query.get_or_404(event_id)
        filename = f"questions_{staff.course.code}_{staff.name.replace(' ', '_')}_{event.title.replace(' ', '_')}.pdf"
        return send_file(BytesIO(pdf_buffer.getvalue()), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)

    @admin_bp.route('/download_student_responses_pdf')
    @login_required
    def download_student_responses_pdf():
        if not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.dashboard'))

        try:
            active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
        except Exception:
            active_event = Event.query.filter_by(is_active=True).first()

        students = Student.query.order_by(Student.roll_number).all()
        responded_ids = set([r[0] for r in db.session.query(FeedbackResponse.student_id).filter_by(event_id=active_event.id).distinct().all()]) if active_event else set()
        data = [['S.No', 'Roll Number', 'Name', 'Response']]

        for idx, student in enumerate(students, 1):
            response = 'Yes' if student.id in responded_ids else 'No'
            data.append([str(idx), student.roll_number, student.name, response])

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        style = getSampleStyleSheet()["Normal"]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        event_title = active_event.title if active_event else 'No Event'
        event_date = active_event.created_at.strftime('%Y-%m-%d') if active_event and active_event.created_at else ''
        pdf_title = f'Student Response Status - {event_title} ({event_date})'
        elements = [Paragraph(pdf_title, style), table]
        doc.build(elements)
        buffer.seek(0)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='student_responses.pdf')

    @admin_bp.route('/download_all_reports')
    @login_required
    def download_all_reports():
        if not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('admin.login'))

        event_id = request.args.get('event_id')
        if not event_id:
            try:
                active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
            except Exception:
                active_event = Event.query.filter_by(is_active=True).first()
            if not active_event:
                flash('No active event found.', 'danger')
                return redirect(url_for('admin.results'))
            event_id = active_event.id
        else:
            event_id = int(event_id)
            active_event = Event.query.get_or_404(event_id)

        staffs = Staff.query.all()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for staff in staffs:
                pdf_buffer = generate_pdf_report(staff.id, event_id=active_event.id)
                pdf_buffer.seek(0)
                filename = f"report_{staff.course.code}_{staff.name.replace(' ', '_')}_{active_event.title.replace(' ', '_')}.pdf"
                zipf.writestr(filename, pdf_buffer.read())

        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='all_reports.zip')
