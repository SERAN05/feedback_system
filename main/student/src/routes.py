from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from src.common.extensions import db
from src.common.models import Student, StudentSession, Event, FeedbackResponse, Course, Staff, Question, QuestionResponse, GeneralFeedback, expire_events
from sqlalchemy.exc import IntegrityError
import secrets

student_bp = Blueprint('student', __name__, url_prefix='/student')


def validate_student_session(student_id):
    """Return (ok, student). If token mismatch -> False and clears session."""
    student = Student.query.get(student_id)
    if not student:
        return False, None
    current = session.get('session_token')
    ss = StudentSession.query.filter_by(student_id=student_id).first()
    if ss and current and ss.token == current:
        return True, student
    # token mismatch -> clear session
    session.pop('student_id', None)
    session.pop('session_token', None)
    return False, None


@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        roll_number = request.form.get('roll_number')
        password = request.form.get('password')
        if not roll_number.startswith('718123') or len(roll_number) != 11 or not roll_number.isdigit():
            flash("Invalid roll number format", "danger")
            return redirect(url_for('student.login'))
        student = Student.query.filter_by(roll_number=roll_number).first()
        if student and student.check_password(password):
            # If there is an existing active session, BLOCK this (second) login
            # so the first logged-in student continues working. Handle a
            # potential race where two logins try to create a session at the
            # same time by catching IntegrityError on commit.
            ss = StudentSession.query.filter_by(student_id=student.id).first()
            if ss:
                flash('This account is already logged in from another device. Please use that session or logout first.', 'warning')
                return redirect(url_for('student.login'))

            # No active session exists — attempt to create one. If another
            # concurrent request creates it first, the commit will raise
            # IntegrityError and we reject the second login.
            token = secrets.token_hex(32)
            ss = StudentSession(student_id=student.id, token=token)
            db.session.add(ss)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('This account is already logged in from another device. Please use that session or logout first.', 'warning')
                return redirect(url_for('student.login'))
            session['student_id'] = student.id
            session['session_token'] = token
            flash("Logged in successfully", "success")
            return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('domains/student/login.html')


@student_bp.route('/logout')
def logout():
    student_id = session.get('student_id')
    if student_id:
        ss = StudentSession.query.filter_by(student_id=student_id).first()
        if ss:
            db.session.delete(ss)
            db.session.commit()
    session.pop('student_id', None)
    session.pop('session_token', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('student.login'))


@student_bp.route('/force_logout', methods=['POST'])
def force_logout():
    """Called via sendBeacon when a student navigates away/close tab.
    Safely remove their StudentSession and clear server session.
    Returns 204 No Content.
    """
    student_id = session.get('student_id')
    if student_id:
        ss = StudentSession.query.filter_by(student_id=student_id).first()
        if ss:
            try:
                db.session.delete(ss)
                db.session.commit()
            except Exception:
                db.session.rollback()
    session.pop('student_id', None)
    session.pop('session_token', None)
    return ('', 204)


@student_bp.route('/check_session')
def check_session():
    student_id = session.get('student_id')
    if not student_id:
        return jsonify({'valid': False, 'message': 'Not logged in'})
    ok, _ = validate_student_session(student_id)
    if ok:
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False, 'message': 'Your account has been logged in somewhere else. Please log in again.'})


@student_bp.route('/dashboard')
def dashboard():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    ok, student = validate_student_session(student_id)
    if not ok:
        flash('Your account has been logged in somewhere else. Please log in again.', 'warning')
        return redirect(url_for('student.login'))
    # Deactivate any events that have reached their end_time before reading
    # the current active event. This ensures events automatically expire.
    expire_events()
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    # Restrict event access by roll number
    event_blocked = False
    warning_message = None
    if active_event and not active_event.is_open_to_all:
        if not (active_event.start_roll_number and active_event.end_roll_number):
            event_blocked = True
            warning_message = active_event.warning_message or "This event is not open to your roll number."
        elif not (active_event.start_roll_number <= student.roll_number <= active_event.end_roll_number):
            event_blocked = True
            warning_message = active_event.warning_message or "This event is not open to your roll number."
    has_submitted = False
    if active_event:
        existing_feedback = FeedbackResponse.query.filter_by(student_id=student_id, event_id=active_event.id).first()
        if existing_feedback:
            has_submitted = True
    return render_template('domains/student/dashboard.html', 
                           student=student,
                           active_event=active_event,
                           has_submitted=has_submitted,
                           event_blocked=event_blocked,
                           warning_message=warning_message)


@student_bp.route('/general-feedback')
def general_feedback_dashboard():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    ok, student = validate_student_session(student_id)
    if not ok:
        flash('Your account has been logged in somewhere else. Please log in again.', 'warning')
        return redirect(url_for('student.login'))
    feedback_history = GeneralFeedback.query.filter_by(student_id=student_id).order_by(GeneralFeedback.timestamp.desc()).all()
    from datetime import timedelta
    return render_template('domains/student/general_feedback_dashboard.html', 
                         student=student,
                         feedback_history=feedback_history,
                         timedelta=timedelta)


@student_bp.route('/submit-feedback/<category>', methods=['GET', 'POST'])
def submit_feedback(category):
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    ok, student = validate_student_session(student_id)
    if not ok:
        flash('Your account has been logged in somewhere else. Please log in again.', 'warning')
        return redirect(url_for('student.login'))

    valid_categories = ['fc', 'library', 'transport', 'sports', 'bookdepot', 'general']
    if category not in valid_categories:
        flash('Invalid feedback category', 'danger')
        return redirect(url_for('student.general_feedback_dashboard'))
    
    category_names = {
        'fc': 'Food Court',
        'library': 'Library',
        'transport': 'Transport',
        'sports': 'Sports',
        'bookdepot': 'Book Depot',
        'general': 'General'
    }
    
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Please provide your feedback before submitting.', 'warning')
            return render_template('domains/student/submit_feedback.html', 
                                 category=category,
                                 category_name=category_names[category],
                                 student=student)
        
        feedback = GeneralFeedback(
            category=category,
            content=content,
            student_id=student_id
        )
        db.session.add(feedback)
        db.session.commit()
        
        flash('Your feedback has been submitted successfully!', 'success')
        return redirect(url_for('student.general_feedback_dashboard'))
    
    return render_template('domains/student/submit_feedback.html', 
                         category=category,
                         category_name=category_names[category],
                         student=student)


@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback_form():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    ok, student = validate_student_session(student_id)
    if not ok:
        flash('Your account has been logged in somewhere else. Please log in again.', 'warning')
        return redirect(url_for('student.login'))

    # Ensure expired events are deactivated before showing the feedback form
    expire_events()
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    # Restrict event access by roll number
    if active_event and not active_event.is_open_to_all:
        if not (active_event.start_roll_number and active_event.end_roll_number):
            flash(active_event.warning_message or "This event is not open to your roll number.", "warning")
            return redirect(url_for('student.dashboard'))
        elif not (active_event.start_roll_number <= student.roll_number <= active_event.end_roll_number):
            flash(active_event.warning_message or "This event is not open to your roll number.", "warning")
            return redirect(url_for('student.dashboard'))
    if not active_event:
        flash('No active feedback event available', 'warning')
        return redirect(url_for('student.dashboard'))
    existing_feedback = FeedbackResponse.query.filter_by(student_id=student_id, event_id=active_event.id).first()
    if existing_feedback:
        flash('You have already submitted feedback for this event', 'warning')
        return redirect(url_for('student.dashboard'))
    if request.method == 'POST':
        courses_data = {}
        courses = active_event.courses
        for course in courses:
            staff_selected = request.form.get(f"staff_{course.id}")
            if staff_selected:
                courses_data[course.id] = {int(staff_selected): {}}
        for key, value in request.form.items():
            if key.startswith('rating_'):
                parts = key.split('_')
                if len(parts) == 4:
                    course_id = int(parts[1])
                    staff_id = list(courses_data.get(course_id, {}).keys())[0] if course_id in courses_data else None
                    question_id = int(parts[3])
                    rating = int(value)
                    if course_id in courses_data and staff_id:
                        courses_data[course_id][staff_id][question_id] = rating
        for course_id, staffs in courses_data.items():
            for staff_id, questions in staffs.items():
                feedback = FeedbackResponse(student_id=student_id,
                                            event_id=active_event.id,
                                            course_id=course_id,
                                            staff_id=staff_id)
                db.session.add(feedback)
                db.session.flush()
                for question_id, rating in questions.items():
                    qr = QuestionResponse(feedback_id=feedback.id,
                                          question_id=question_id,
                                          rating=rating)
                    db.session.add(qr)
        db.session.commit()
        flash('Feedback submitted successfully', 'success')
        return redirect(url_for('student.thank_you'))
    courses = active_event.courses
    questions = Question.query.filter_by(is_archived=False).all()
    course_staffs = {}
    for course in courses:
        course_staffs[course.id] = Staff.query.filter_by(course_id=course.id).all()
    return render_template('domains/student/feedback_form.html',
                           student=student,
                           event=active_event,
                           courses=courses,
                           questions=questions,
                           course_staffs=course_staffs)


@student_bp.route('/thank-you')
def thank_you():
    if not session.get('student_id'):
        return redirect(url_for('student.login'))
    ok, _ = validate_student_session(session.get('student_id'))
    if not ok:
        flash('Your account has been logged in somewhere else. Please log in again.', 'warning')
        return redirect(url_for('student.login'))
    return render_template('domains/student/thank_you.html')
