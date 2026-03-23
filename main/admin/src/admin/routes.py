import os
import smtplib
from email.mime.text import MIMEText

import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, login_user, logout_user, current_user
from sqlalchemy import func, inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from src.common.extensions import db
from src.common.models import User, Student, Event, Course, Staff, Question, FeedbackResponse, QuestionResponse, GeneralFeedback
from datetime import datetime, timezone
from summarizer import summarize_feedback
from src.common.utils.excel_handler import allowed_file, validate_student_excel, validate_course_staff_excel
from src.common.utils.pdf_generator import generate_summary_pdf

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def safe_filter(query_obj):
    try:
        entity = query_obj.column_descriptions[0]['entity']
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(entity.__tablename__)]
        if 'is_deleted' in columns:
            return query_obj.filter_by(is_deleted=False)
    except Exception:
        pass
    return query_obj


def _get_event_recipient_emails(event):
    query = Student.query
    if not event.is_open_to_all:
        if not event.start_roll_number or not event.end_roll_number:
            return []
        query = query.filter(
            Student.roll_number >= event.start_roll_number,
            Student.roll_number <= event.end_roll_number
        )

    emails = []
    for student in query.all():
        email = (student.email or '').strip()
        if email and '@' in email:
            emails.append(email)

    return sorted(set(emails))


def _send_event_start_notifications(event, login_url):
    smtp_host = current_app.config.get('SMTP_HOST')
    smtp_port = current_app.config.get('SMTP_PORT', 587)
    smtp_username = current_app.config.get('SMTP_USERNAME')
    smtp_password = current_app.config.get('SMTP_PASSWORD')
    smtp_use_tls = current_app.config.get('SMTP_USE_TLS', True)
    smtp_use_ssl = current_app.config.get('SMTP_USE_SSL', False)
    smtp_timeout = current_app.config.get('SMTP_TIMEOUT', 30)
    mail_from = current_app.config.get('MAIL_FROM') or smtp_username

    if not smtp_host or not mail_from:
        return False, 'Event was started, but email is not configured. Set SMTP_HOST and MAIL_FROM (or SMTP_USERNAME).'

    recipient_emails = _get_event_recipient_emails(event)
    if not recipient_emails:
        return True, 'Event was started. No student email recipients found for this event.'

    subject = f'New Feedback Event: {event.title}'
    body = (
        f'Hello Student,\n\n'
        f'A new feedback event has been started: "{event.title}".\n'
        f'Please log in and submit your feedback using the student portal link below:\n\n'
        f'{login_url}\n\n'
        f'Thank you.'
    )

    message = MIMEText(body, 'plain', 'utf-8')
    message['Subject'] = subject
    message['From'] = mail_from
    message['To'] = ', '.join(recipient_emails)

    try:
        if smtp_use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout)

        with server:
            if smtp_use_tls and not smtp_use_ssl:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.sendmail(mail_from, recipient_emails, message.as_string())

        return True, f'Email notification sent to {len(recipient_emails)} student(s).'
    except Exception as exc:
        current_app.logger.exception('Failed to send event start emails')
        return False, f'Event was started, but failed to send emails: {exc}'


@admin_bp.route('/api/download-sentiment-pdf', methods=['POST'])
@login_required
def download_sentiment_pdf():
    import logging
    try:
        if not current_user.is_admin:
            logging.error('Access denied: not admin')
            return jsonify({'error': 'Access denied'}), 403
        data = request.get_json()
        category = data.get('category', 'all')
        if category == 'all':
            feedbacks = GeneralFeedback.query.order_by(GeneralFeedback.timestamp.desc()).all()
        else:
            feedbacks = GeneralFeedback.query.filter_by(category=category).order_by(GeneralFeedback.timestamp.desc()).all()
        feedback_texts = [fb.content for fb in feedbacks if fb.content]
        if not feedback_texts:
            logging.warning(f'No feedbacks found for category: {category}')
            return jsonify({'error': 'No feedbacks found for this category.'}), 400
        from src.common.utils.sentiment_pdf import generate_sentiment_pdf
        pdf_bytes = generate_sentiment_pdf(feedback_texts, category)
        if not pdf_bytes or pdf_bytes.getbuffer().nbytes == 0:
            logging.error('PDF generation failed or empty PDF')
            return jsonify({'error': 'PDF generation failed.'}), 500
        return send_file(
            pdf_bytes,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Sentiment_Report_{category}.pdf'
        )
    except Exception as e:
        logging.exception('Error in download_sentiment_pdf')
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@admin_bp.route('/api/download-summary-pdf', methods=['POST'])
@login_required
def download_summary_pdf():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    data = request.get_json()
    category = data.get('category')
    summary = data.get('summary')
    if not category or not summary:
        return jsonify({'error': 'Category and summary required'}), 400
    pdf_bytes = generate_summary_pdf(category, summary)
    return send_file(
        pdf_bytes,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'AI_Summary_{category}.pdf'
    )


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip()

        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user and user.check_password(password) and user.is_admin:
            login_user(user, remember=False)
            flash("Logged in successfully", "success")
            return redirect(url_for('admin.dashboard'))

        # Fallback for default admin credentials in case seed data drifted.
        default_username = 'Admin@srec/123'
        default_password = 'Admin/cse.srec@ac.in'
        if username == default_username and password == default_password:
            admin_user = User.query.filter_by(is_admin=True).first()
            if not admin_user:
                admin_user = User(
                    username=default_username,
                    password_hash=generate_password_hash(default_password, method='pbkdf2:sha256'),
                    is_admin=True
                )
                db.session.add(admin_user)
            else:
                admin_user.username = default_username
                admin_user.password_hash = generate_password_hash(default_password, method='pbkdf2:sha256')

            db.session.commit()
            login_user(admin_user, remember=False)
            flash("Logged in successfully", "success")
            return redirect(url_for('admin.dashboard'))

        flash('Invalid username or password', 'danger')
    return render_template('domains/admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for('admin.login'))


@admin_bp.route('/api/debug-events')
@login_required
def debug_events():
    """Debug endpoint to check events and feedback data"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        events = safe_filter(Event.query).all()
        debug_info = []
        
        for event in events:
            feedback_count = FeedbackResponse.query.filter_by(event_id=event.id).count()
            distinct_students = db.session.query(FeedbackResponse.student_id)\
                .filter(FeedbackResponse.event_id == event.id)\
                .distinct()\
                .count()
            
            debug_info.append({
                'event_id': event.id,
                'event_title': event.title,
                'is_active': event.is_active,
                'total_feedback_records': feedback_count,
                'distinct_students': distinct_students
            })
        
        return jsonify({
            'total_events': len(events),
            'total_students': Student.query.count(),
            'total_feedback_responses': FeedbackResponse.query.count(),
            'events': debug_info
        })
    except Exception as e:
        import logging
        logging.error(f"Debug error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/event-stats/<int:event_id>')
@login_required
def get_event_stats(event_id):
    """Fetch statistics for a specific event (active or past)"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        print(f"\n=== DEBUG: get_event_stats called with event_id={event_id} (type: {type(event_id).__name__}) ===")
        logger.warning(f"DEBUG: get_event_stats called with event_id={event_id} (type: {type(event_id).__name__})")
        
        # Get the event
        event = Event.query.filter_by(id=event_id).first()
        if not event:
            print(f"Event {event_id} not found in database")
            logger.warning(f"Event {event_id} not found in database")
            return jsonify({'error': f'Event {event_id} not found'}), 404
        
        print(f"Found event: {event.title} (ID: {event.id}, is_active: {event.is_active})")
        logger.warning(f"Found event: {event.title} (ID: {event.id}, type: {type(event.id).__name__})")
        
        total_students = Student.query.count()
        print(f"Total students in system: {total_students}")
        
        # Query ALL FeedbackResponse records first to see what we have
        all_feedback = FeedbackResponse.query.all()
        print(f"Total FeedbackResponse records in database: {len(all_feedback)}")
        for fr in all_feedback[:5]:
            print(f"  - FeedbackResponse: id={fr.id}, event_id={fr.event_id} (type: {type(fr.event_id).__name__}), student_id={fr.student_id}")
        
        # Now query for THIS specific event
        feedback_responses = FeedbackResponse.query.filter(FeedbackResponse.event_id == int(event_id)).all()
        print(f"FeedbackResponse records for event_id={event_id}: {len(feedback_responses)}")
        for fr in feedback_responses:
            print(f"  - Found: id={fr.id}, event_id={fr.event_id}, student_id={fr.student_id}")
        
        logger.warning(f"Total FeedbackResponse for event {event_id}: {len(feedback_responses)}")
        
        # Get unique student IDs who responded
        responded_student_ids = set()
        for fr in feedback_responses:
            responded_student_ids.add(fr.student_id)
        
        event_responses = len(responded_student_ids)
        print(f"Distinct students who responded: {event_responses}")
        logger.warning(f"Distinct students who responded: {event_responses}")
        
        completion_rate = (event_responses / total_students * 100) if total_students > 0 else 0
        
        response_data = {
            'event_id': event.id,
            'event_title': event.title,
            'is_active': event.is_active,
            'event_responses': event_responses,
            'total_students': total_students,
            'completion_rate': round(completion_rate, 1),
            'pending_responses': total_students - event_responses
        }
        print(f"Returning response: {response_data}\n")
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error fetching event stats: {str(e)}", exc_info=True)
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error: ' + str(e)}), 500
@admin_bp.route('/api/student-responses/<int:event_id>')
@login_required
def get_student_responses(event_id):
    """Fetch student response status for a specific event"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get the event
        event = Event.query.filter_by(id=event_id).first()
        if not event:
            return jsonify({'error': f'Event {event_id} not found'}), 404
        
        # Get all students
        students = Student.query.order_by(Student.roll_number).all()
        
        # Get students who responded to this event
        responded_ids = set()
        feedback_responses = FeedbackResponse.query.filter(FeedbackResponse.event_id == int(event_id)).all()
        for fr in feedback_responses:
            responded_ids.add(fr.student_id)
        
        # Build response data
        student_responses = []
        for idx, student in enumerate(students, 1):
            is_responded = student.id in responded_ids
            student_responses.append({
                'index': idx,
                'roll_number': student.roll_number,
                'name': student.name,
                'responded': is_responded,
                'status': 'yes' if is_responded else 'no'
            })
        
        return jsonify({
            'event_id': event.id,
            'event_title': event.title,
            'students': student_responses,
            'total_students': len(students),
            'responded_count': len(responded_ids)
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching student responses: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error: ' + str(e)}), 500

@admin_bp.route('/api/delete-event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    """Delete an event and all its associated feedback data"""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get the event
        event = Event.query.filter_by(id=event_id).first()
        if not event:
            return jsonify({'error': f'Event {event_id} not found'}), 404
        
        event_title = event.title
        
        # Delete all feedback responses associated with this event
        feedback_responses = FeedbackResponse.query.filter_by(event_id=event_id).all()
        for feedback in feedback_responses:
            db.session.delete(feedback)
        
        print(f"Deleted {len(feedback_responses)} feedback responses for event {event_id}")
        
        # Delete the event itself
        db.session.delete(event)
        db.session.commit()
        
        print(f"Event '{event_title}' (ID: {event_id}) deleted successfully")
        
        return jsonify({
            'success': True,
            'message': f'Event "{event_title}" and all associated data deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting event: {str(e)}", exc_info=True)
        print(f"ERROR deleting event: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error: ' + str(e)}), 500

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to view this page.', 'danger')
        return redirect(url_for('admin.login'))
    # Ensure `end_time` column exists on the `event` table (SQLite ALTER if needed)
    try:
        db.session.execute(text("SELECT end_time FROM event LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text("ALTER TABLE event ADD COLUMN end_time DATETIME"))
            db.session.commit()
        except Exception:
            db.session.rollback()
    # Ensure `semester` and `event_type` columns exist on the `event` table
    try:
        db.session.execute(text("SELECT semester FROM event LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text("ALTER TABLE event ADD COLUMN semester INTEGER"))
            db.session.commit()
        except Exception:
            db.session.rollback()
    try:
        db.session.execute(text("SELECT event_type FROM event LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text("ALTER TABLE event ADD COLUMN event_type VARCHAR(50)"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    events = safe_filter(Event.query).all()
    total_students = Student.query.count()
    total_responses = FeedbackResponse.query.count()
    total_general_feedback = GeneralFeedback.query.count()
    active_event = safe_filter(Event.query.filter_by(is_active=True)).first()
    
    # Separate active and past events
    active_events = [e for e in events if e.is_active]
    past_events = [e for e in events if not e.is_active]
    
    event_responses = 0
    completion_rate = 0
    students = Student.query.order_by(Student.roll_number).all()
    responded_ids = set([r[0] for r in db.session.query(FeedbackResponse.student_id).filter_by(event_id=active_event.id).distinct().all()]) if active_event else set()
    if total_students > 0 and active_event:
        event_responses = db.session.query(FeedbackResponse.student_id).filter_by(event_id=active_event.id).distinct().count()
        completion_rate = (event_responses / total_students) * 100
    return render_template('domains/admin/dashboard.html', events=events,
                           total_students=total_students, total_responses=total_responses,
                           total_general_feedback=total_general_feedback,
                           active_event=active_event, completion_rate=completion_rate, event_responses=event_responses,
                           active_events=active_events, past_events=past_events,
                           students=students, responded_ids=responded_ids)


@admin_bp.route('/general-feedback')
@login_required
def general_feedback():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))

    category_filter = request.args.get('category', 'all')

    if category_filter == 'all':
        feedbacks = GeneralFeedback.query.order_by(GeneralFeedback.timestamp.desc()).all()
    else:
        feedbacks = GeneralFeedback.query.filter_by(category=category_filter).order_by(GeneralFeedback.timestamp.desc()).all()

    category_stats = {}
    categories = ['fc', 'library', 'transport', 'sports', 'bookdepot', 'general']
    for cat in categories:
        category_stats[cat] = GeneralFeedback.query.filter_by(category=cat).count()

    category_names = {
        'fc': 'Food Court',
        'library': 'Library',
        'transport': 'Transport',
        'sports': 'Sports',
        'bookdepot': 'Book Depot',
        'general': 'General'
    }

    from datetime import timedelta
    return render_template('domains/admin/general_feedback.html',
                           feedbacks=feedbacks,
                           category_filter=category_filter,
                           category_stats=category_stats,
                           category_names=category_names,
                           timedelta=timedelta)


@admin_bp.route('/api/general-feedback-summary', methods=['POST'])
@login_required
def general_feedback_summary():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    data = request.get_json()
    category = data.get('category')
    if not category:
        return jsonify({'error': 'Category required'}), 400
    comments = [fb.content for fb in GeneralFeedback.query.filter_by(category=category).all()]
    summary = summarize_feedback(category, comments)
    return jsonify({'summary': summary})


@admin_bp.route('/general-feedback/<int:feedback_id>/resolve', methods=['POST'])
@login_required
def resolve_general_feedback(feedback_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))

    feedback = GeneralFeedback.query.get_or_404(feedback_id)
    response = request.form.get('response', '')

    feedback.is_resolved = True
    feedback.admin_response = response
    db.session.commit()

    flash('Feedback marked as resolved.', 'success')
    return redirect(url_for('admin.general_feedback'))


@admin_bp.route('/api/general-feedback-stats')
@login_required
def general_feedback_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403

    from datetime import datetime, timedelta
    monthly_data = []
    category_data = {}

    categories = ['fc', 'library', 'transport', 'sports', 'bookdepot', 'general']

    for i in range(6):
        start_date = datetime.utcnow().replace(day=1) - timedelta(days=30 * i)
        end_date = start_date.replace(day=28) + timedelta(days=4)
        end_date = end_date - timedelta(days=end_date.day)

        total_count = GeneralFeedback.query.filter(
            GeneralFeedback.timestamp >= start_date,
            GeneralFeedback.timestamp <= end_date
        ).count()

        monthly_data.append({
            'month': start_date.strftime('%b %Y'),
            'count': total_count
        })

    for cat in categories:
        category_data[cat] = GeneralFeedback.query.filter_by(category=cat).count()

    return jsonify({
        'monthly_data': list(reversed(monthly_data)),
        'category_data': category_data
    })


@admin_bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin.', 'danger')
        return redirect(url_for('admin.login'))
    # Ensure `end_time` column exists on the `event` table (SQLite ALTER if needed)
    try:
        db.session.execute(text("SELECT end_time FROM event LIMIT 1"))
    except Exception:
        try:
            db.session.execute(text("ALTER TABLE event ADD COLUMN end_time DATETIME"))
            db.session.commit()
        except Exception:
            db.session.rollback()
    # expire events whose end_time has passed
    try:
        now = datetime.utcnow()
        expired = Event.query.filter(Event.end_time != None, Event.end_time <= now, Event.is_active == True).all()
        for ev in expired:
            ev.is_active = False
        if expired:
            db.session.commit()
    except Exception:
        db.session.rollback()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            title = request.form.get('title')
            description = request.form.get('description')
            # new fields
            semester_str = request.form.get('semester')
            event_type = request.form.get('event_type')
            end_time_str = request.form.get('end_time')
            additional_questions = request.form.get('additional_questions')
            warning_message = request.form.get('warning_message')
            is_open_to_all = request.form.get('is_open_to_all') == 'on'
            start_roll_number = request.form.get('start_roll_number') if not is_open_to_all else None
            end_roll_number = request.form.get('end_roll_number') if not is_open_to_all else None
            course_ids = request.form.getlist('course_ids')
            if not title:
                flash('Event title is required', 'danger')
                return redirect(url_for('admin.manage_events'))
            # parse end_time if provided
            end_time = None
            if end_time_str:
                try:
                    # datetime-local input provides something like 'YYYY-MM-DDTHH:MM'
                    naive = datetime.fromisoformat(end_time_str)
                    # assume naive is in server local timezone; convert to UTC before storing
                    local_tz = datetime.now().astimezone().tzinfo
                    local_aware = naive.replace(tzinfo=local_tz)
                    end_time_utc = local_aware.astimezone(timezone.utc)
                    # store as naive UTC to match existing created_at behavior
                    end_time = end_time_utc.replace(tzinfo=None)
                except Exception:
                    end_time = None
            # end_time, if provided, must be in the future
            if end_time and end_time <= datetime.utcnow():
                flash('End date/time must be in the future', 'danger')
                return redirect(url_for('admin.manage_events'))

            # parse semester to integer if provided and valid (1-8)
            semester = None
            try:
                if semester_str:
                    sem_val = int(semester_str)
                    if 1 <= sem_val <= 8:
                        semester = sem_val
            except Exception:
                semester = None

            event = Event(
                title=title,
                description=description,
                warning_message=warning_message,
                is_active=False,
                end_time=end_time,
                is_open_to_all=is_open_to_all,
                start_roll_number=start_roll_number,
                end_roll_number=end_roll_number,
                semester=semester,
                event_type=event_type
            )
            if course_ids:
                event.courses = Course.query.filter(Course.id.in_(course_ids)).all()
            db.session.add(event)
            db.session.commit()
            flash('Event created successfully', 'success')
            if additional_questions:
                questions_list = [q.strip() for q in additional_questions.splitlines() if q.strip()]
                for q_text in questions_list:
                    existing = Question.query.filter_by(text=q_text).first()
                    if not existing:
                        db.session.add(Question(text=q_text))
                db.session.commit()
                flash(f"Added {len(questions_list)} additional question(s).", "success")
        elif action == 'toggle':
            event_id = request.form.get('event_id')
            event = Event.query.get_or_404(event_id)
            Event.query.update({Event.is_active: False})
            activating_event = request.form.get('is_active') == 'true'
            if activating_event:
                event.is_active = True
            db.session.commit()
            flash(f'Event "{event.title}" status updated', 'success')
            if activating_event:
                login_url = current_app.config.get('STUDENT_LOGIN_URL') or url_for('student.login', _external=True)
                sent_ok, sent_message = _send_event_start_notifications(event, login_url)
                flash(sent_message, 'success' if sent_ok else 'warning')
        elif action == 'delete':
            event_id = request.form.get('event_id')
            event = Event.query.get_or_404(event_id)
            event.is_deleted = True
            db.session.commit()
            flash('Event was moved to Past Responses.', 'success')
    events = safe_filter(Event.query).all()
    # Prepare human-friendly local timezone display strings for created_at and end_time
    try:
        local_tz = datetime.now().astimezone().tzinfo
        for ev in events:
            if ev.created_at:
                try:
                    created_utc = ev.created_at.replace(tzinfo=timezone.utc)
                    ev.display_created = created_utc.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ev.display_created = ev.created_at.strftime('%Y-%m-%d %H:%M')
            else:
                ev.display_created = 'N/A'
            if getattr(ev, 'end_time', None):
                try:
                    end_utc = ev.end_time.replace(tzinfo=timezone.utc)
                    ev.display_end = end_utc.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    ev.display_end = ev.end_time.strftime('%Y-%m-%d %H:%M')
            else:
                ev.display_end = None
    except Exception:
        for ev in events:
            ev.display_created = ev.created_at.strftime('%Y-%m-%d %H:%M') if ev.created_at else 'N/A'
            ev.display_end = ev.end_time.strftime('%Y-%m-%d %H:%M') if getattr(ev, 'end_time', None) else None
    courses = Course.query.all()
    questions = Question.query.filter_by(is_archived=False).all()
    return render_template('domains/admin/manage_events.html', events=events, questions=questions, courses=courses)


@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    q = Question.query.get_or_404(question_id)
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    if active_event:
        flash("Cannot delete while an event is active. Deactivate the event first.", "danger")
        return redirect(url_for('admin.manage_events'))
    if q.responses and len(q.responses) > 0:
        q.is_archived = True
        db.session.commit()
        flash("Question archived (has responses) and will no longer appear in new feedback.", "info")
    else:
        db.session.delete(q)
        db.session.commit()
        flash("Question deleted successfully.", "success")
    return redirect(url_for('admin.manage_events'))


@admin_bp.route('/past_responses')
@login_required
def past_responses():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))
    try:
        past_events = Event.query.filter_by(is_deleted=True).all()
    except Exception:
        past_events = []
    return render_template('domains/admin/past_responses.html', past_events=past_events)


@admin_bp.route('/force_logout', methods=['POST'])
@login_required
def force_logout_all():
    """Admin endpoint to force-logout all students (clear StudentSession table)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    from src.common.models import StudentSession
    try:
        StudentSession.query.delete()
        db.session.commit()
        return jsonify({'ok': True}), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to clear sessions'}), 500


@admin_bp.route('/courses', methods=['GET', 'POST'])
@login_required
def manage_courses():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create_course':
            code = request.form.get('code')
            name = request.form.get('name')
            if not code or not name:
                flash('Course code and name are required', 'danger')
                return redirect(url_for('admin.manage_courses'))
            if Course.query.filter_by(code=code).first():
                flash('Course code already exists', 'danger')
                return redirect(url_for('admin.manage_courses'))
            course = Course(code=code, name=name)
            db.session.add(course)
            db.session.commit()
            flash('Course created successfully', 'success')
        elif action == 'add_staff':
            course_id = request.form.get('course_id')
            staff_name = request.form.get('staff_name')
            if not course_id or not staff_name:
                flash('Course and staff name are required', 'danger')
                return redirect(url_for('admin.manage_courses'))
            course = Course.query.get_or_404(course_id)
            staff = Staff(name=staff_name, course_id=course.id)
            db.session.add(staff)
            db.session.commit()
            flash('Staff added successfully', 'success')
        elif action == 'delete_course':
            course_id = request.form.get('course_id')
            course = Course.query.get_or_404(course_id)
            if FeedbackResponse.query.filter_by(course_id=course.id).count() > 0:
                flash('Cannot delete course with existing responses', 'danger')
            else:
                Staff.query.filter_by(course_id=course.id).delete()
                db.session.delete(course)
                db.session.commit()
                flash('Course deleted successfully', 'success')
        elif action == 'delete_staff':
            staff_id = request.form.get('staff_id')
            staff = Staff.query.get_or_404(staff_id)
            if FeedbackResponse.query.filter_by(staff_id=staff.id).count() > 0:
                flash('Cannot delete staff with existing responses', 'danger')
            else:
                db.session.delete(staff)
                db.session.commit()
                flash('Staff deleted successfully', 'success')
        elif action == 'upload_courses':
            if 'file' not in request.files:
                flash('No file part', 'danger')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                try:
                    success, message, data = validate_course_staff_excel(file)
                    if not success:
                        flash(message, 'danger')
                        return redirect(request.url)
                    added_courses = 0
                    added_staff = 0
                    for course_code, course_name, teacher_name in data:
                        course = Course.query.filter_by(code=course_code, name=course_name).first()
                        if not course:
                            course = Course(code=course_code, name=course_name)
                            db.session.add(course)
                            db.session.commit()
                            added_courses += 1
                        staff = Staff.query.filter_by(name=teacher_name, course_id=course.id).first()
                        if not staff:
                            staff = Staff(name=teacher_name, course_id=course.id)
                            db.session.add(staff)
                            db.session.commit()
                            added_staff += 1
                    flash(f"{message}. Added {added_courses} new courses and {added_staff} new staff.", 'success')
                except Exception as e:
                    flash(f'Error processing file: {str(e)}', 'danger')
            else:
                flash('Invalid file type. Please upload an Excel file (.xls, .xlsx)', 'danger')
    courses = Course.query.all()
    return render_template('domains/admin/manage_courses.html', courses=courses)


@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required
def manage_students():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'upload':
            if 'file' not in request.files:
                flash('No file part', 'danger')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'danger')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                try:
                    success, message, students_data = validate_student_excel(file)
                    if not success:
                        flash(message, 'danger')
                        return redirect(request.url)
                    # Deduplicate rows from the uploaded file by roll number so
                    # repeated rows do not cause unique-key insert failures.
                    deduped_students = {}
                    for roll_number, name, email in students_data:
                        deduped_students[roll_number] = (name, email)

                    if len(deduped_students) < len(students_data):
                        duplicate_count = len(students_data) - len(deduped_students)
                        flash(f'Skipped {duplicate_count} duplicate row(s) in uploaded file (same roll number).', 'warning')

                    roll_numbers = list(deduped_students.keys())
                    existing_students = Student.query.filter(Student.roll_number.in_(roll_numbers)).all()
                    existing_by_roll = {s.roll_number: s for s in existing_students}

                    for roll_number, (name, email) in deduped_students.items():
                        existing_student = existing_by_roll.get(roll_number)
                        if existing_student:
                            existing_student.name = name
                            existing_student.email = email
                        else:
                            new_student = Student(
                                roll_number=roll_number,
                                name=name,
                                email=email,
                                password_hash=generate_password_hash('Srec@123', method='pbkdf2:sha256')
                            )
                            db.session.add(new_student)
                    db.session.commit()
                    flash(f'Successfully processed {len(deduped_students)} students', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error processing file: {str(e)}', 'danger')
        elif action == 'add_student':
            roll_number = request.form.get('roll_number')
            name = request.form.get('name')
            if not roll_number.startswith('718123') or len(roll_number) != 11:
                flash('Roll number must start with 718123 and be 11 digits long', 'danger')
                return redirect(url_for('admin.manage_students'))
            if Student.query.filter_by(roll_number=roll_number).first():
                flash('Student with this roll number already exists', 'danger')
                return redirect(url_for('admin.manage_students'))
            new_student = Student(
                roll_number=roll_number,
                name=name,
                password_hash=generate_password_hash('Srec@123', method='pbkdf2:sha256')
            )
            db.session.add(new_student)
            db.session.commit()
            flash('Student added successfully', 'success')
        elif action == 'delete_student':
            student_id = request.form.get('student_id')
            s = Student.query.get_or_404(student_id)
            if FeedbackResponse.query.filter_by(student_id=s.id).count() > 0:
                flash('Cannot delete student with existing responses', 'danger')
            else:
                db.session.delete(s)
                db.session.commit()
                flash('Student deleted successfully', 'success')
        elif action == 'delete_all':
            students = Student.query.all()
            count_deleted = 0
            for s in students:
                db.session.delete(s)
                count_deleted += 1
            db.session.commit()
            flash(f"Deleted {count_deleted} students.", "success")
    students = Student.query.all()
    return render_template('domains/admin/manage_students.html', students=students)


