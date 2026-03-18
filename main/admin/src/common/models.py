from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from src.common.extensions import db, login_manager
from sqlalchemy.orm import relationship
from sqlalchemy import Table, Column, Integer, ForeignKey

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_incharge = db.Column(db.Boolean, default=False)
    incharge_category = db.Column(db.String(50), nullable=True)  # fc, library, transport, sports, bookdepot

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# New General Feedback Model
class GeneralFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # fc, library, transport, sports, bookdepot, general
    content = db.Column(db.Text, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship('Student', backref='general_feedbacks')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)
    admin_response = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<GeneralFeedback {self.category}: {self.id}>'
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False,
                              default=generate_password_hash('Srec@123', method='pbkdf2:sha256'))
    feedback_responses = db.relationship('FeedbackResponse', backref='student', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Student {self.roll_number}>'


class StudentSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False, unique=True)
    token = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('session', uselist=False))

    def __repr__(self):
        return f'<StudentSession {self.student_id}>'

# Association table for Event <-> Course
EventCourse = Table('event_course', db.Model.metadata,
    Column('event_id', Integer, ForeignKey('event.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('course.id'), primary_key=True)
)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    warning_message = db.Column(db.Text, default='This feedback is for the specified class only.')
    is_active = db.Column(db.Boolean, default=False)
    end_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)   
    is_open_to_all = db.Column(db.Boolean, default=True)
    start_roll_number = db.Column(db.String(20), nullable=True)
    end_roll_number = db.Column(db.String(20), nullable=True)
    # New: semester (1-8) and event type (mid-sem, course-end, etc.)
    semester = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(50), nullable=True)
    feedback_responses = db.relationship('FeedbackResponse', backref='event', lazy=True)
    # New: courses for this event
    courses = db.relationship('Course', secondary=EventCourse, backref='events')

    def __repr__(self):
        return f'<Event {self.title}>'


def expire_events():
    """Deactivate events whose end_time (stored in UTC) has passed.
    This is a lightweight helper you can call from request handlers to
    ensure events are deactivated without relying on a background worker.
    """
    from datetime import datetime
    now = datetime.utcnow()
    try:
        expired = Event.query.filter(Event.is_active == True, Event.end_time != None, Event.end_time <= now).all()
        if not expired:
            return
        for ev in expired:
            ev.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    staffs = db.relationship('Staff', backref='course', lazy=True)
    feedback_responses = db.relationship('FeedbackResponse', backref='course', lazy=True)

    def __repr__(self):
        return f'<Course {self.code} - {self.name}>'

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    feedback_responses = db.relationship('FeedbackResponse', backref='staff', lazy=True)

    def __repr__(self):
        return f'<Staff {self.name}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    responses = db.relationship('QuestionResponse', backref='question', lazy=True)
    # Soft archive so historical responses remain intact
    is_archived = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Question {self.id}: {self.text[:20]}...>'

class FeedbackResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    question_responses = db.relationship('QuestionResponse', backref='feedback', lazy=True,
                                          cascade='all, delete-orphan')

    def __repr__(self):
        return f'<FeedbackResponse {self.id}>'

class QuestionResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feedback_id = db.Column(db.Integer, db.ForeignKey('feedback_response.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 4

    def __repr__(self):
        return f'<QuestionResponse {self.id}: Rating {self.rating}>'
