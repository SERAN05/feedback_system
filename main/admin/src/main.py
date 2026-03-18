import os
import threading
import time
from flask import Flask, render_template
from flask_migrate import Migrate
from src.common.config import Config
from src.common.extensions import db, login_manager
from sqlalchemy import text
from datetime import datetime
from flask_login import current_user

migrate = Migrate()

def create_app(config_class=Config):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static'),
        instance_path=os.path.join(base_dir, 'instance')
    )
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'admin.login'
    login_manager.login_message_category = 'info'

    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)

    # Add moment function to template context
    @app.template_global()
    def moment():
        class MomentWrapper:
            def __init__(self):
                self.dt = datetime.now()
            
            def format(self, format_string):
                # Convert moment.js format to Python strftime format
                format_map = {
                    'MMM DD, YYYY HH:mm': '%b %d, %Y %H:%M',
                    'MMM DD, YYYY': '%b %d, %Y',
                    'DD/MM/YYYY': '%d/%m/%Y',
                    'YYYY-MM-DD': '%Y-%m-%d',
                    'HH:mm': '%H:%M'
                }
                python_format = format_map.get(format_string, '%b %d, %Y %H:%M')
                return self.dt.strftime(python_format)
        
        return MomentWrapper()

    from src.admin.routes import admin_bp
    from src.student.routes import student_bp
    from src.incharge.routes import incharge_bp
    from src.results.routes import register_results_routes

    register_results_routes(admin_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(incharge_bp)

    with app.app_context():
        from src.common.models import User, Student, Event, Course, Staff, Question, FeedbackResponse, GeneralFeedback
        db.create_all()

        # Ensure new columns exist on `event` table before any queries run
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

        # Create admin and default questions if not present
        admin_username = 'Admin@srec/123'
        admin_password = 'Admin/cse.srec@ac.in'
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(username=admin_username,
                         password_hash=generate_password_hash(admin_password),
                         is_admin=True)
            db.session.add(admin)
        else:
            from werkzeug.security import generate_password_hash
            admin.username = admin_username
            admin.password_hash = generate_password_hash(admin_password)

        # Create default in-charge users
        from werkzeug.security import generate_password_hash
        incharge_categories = ['fc', 'library', 'transport', 'sports', 'bookdepot']
        for category in incharge_categories:
            existing_incharge = User.query.filter_by(username=category, is_incharge=True).first()
            incharge_password = f'{category}@srec.ac.in'
            if not existing_incharge:
                incharge = User(
                    username=category,
                    password_hash=generate_password_hash(incharge_password),
                    is_incharge=True,
                    incharge_category=category
                )
                db.session.add(incharge)
            else:
                existing_incharge.password_hash = generate_password_hash(incharge_password)

        questions_text = [
            "How would you rate the clarity of course objectives?",
            "How would you rate the organization of course content?",
            "How would you rate the relevance of course materials?",
            "How would you rate the availability of learning resources?",
            "How would you rate the instructor's knowledge of the subject?",
            "How would you rate the instructor's teaching methods?",
            "How would you rate the instructor's responsiveness to questions?",
            "How would you rate the clarity of assessment criteria?",
            "How would you rate the fairness of grading?",
            "How would you rate the timeliness of feedback?",
            "How would you rate the practical application of concepts?",
            "How would you rate the classroom/online learning environment?",
            "How would you rate the overall course difficulty?",
            "How would you rate the effectiveness of labs/assignments?",
            "How would you rate your overall satisfaction with this course?"
        ]
        from src.common.models import Question
        existing_ids = {q.id for q in Question.query.with_entities(Question.id).all()}
        for i, q_text in enumerate(questions_text, start=1):
            if i in existing_ids:
                continue
            db.session.add(Question(id=i, text=q_text))
        db.session.commit()

        # Start a background thread to expire events automatically.
        # Only start when running the actual server process (avoid starting
        # twice because of the Flask reloader). The WERKZEUG_RUN_MAIN env var
        # is set to 'true' in the child process where the app actually runs.
        def _start_expire_worker():
            from src.common.models import expire_events
            def worker():
                while True:
                    try:
                        expire_events()
                    except Exception:
                        pass
                    time.sleep(30)
            t = threading.Thread(target=worker, daemon=True)
            t.start()

        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
            _start_expire_worker()

    @app.route('/')
    def index():
        return render_template('base.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
