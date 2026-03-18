from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from src.common.extensions import db
from src.common.models import User, GeneralFeedback, Student
from datetime import datetime, timedelta

incharge_bp = Blueprint('incharge', __name__, url_prefix='/incharge')

@incharge_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        
        # Check if it's a valid incharge login
        valid_categories = ['fc', 'library', 'transport', 'sports', 'bookdepot']
        if username in valid_categories and password == f"{username}@srec.ac.in":
            # Find or create incharge user
            user = User.query.filter_by(username=username, is_incharge=True).first()
            if not user:
                from werkzeug.security import generate_password_hash
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
                    is_incharge=True,
                    incharge_category=username
                )
                db.session.add(user)
                db.session.commit()
            
            login_user(user, remember=False)
            flash("Logged in successfully", "success")
            return redirect(url_for('incharge.dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('domains/incharge/login.html')

@incharge_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for('incharge.login'))

@incharge_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_incharge:
        flash('Access denied. You must be an in-charge to view this page.', 'danger')
        return redirect(url_for('incharge.login'))
    
    category = current_user.incharge_category
    
    # Get feedback for this category
    feedbacks = GeneralFeedback.query.filter_by(category=category).order_by(GeneralFeedback.timestamp.desc()).all()
    
    # Statistics
    total_feedbacks = len(feedbacks)
    recent_feedbacks = GeneralFeedback.query.filter_by(category=category).filter(
        GeneralFeedback.timestamp >= datetime.utcnow() - timedelta(days=7)
    ).count()
    resolved_feedbacks = GeneralFeedback.query.filter_by(category=category, is_resolved=True).count()
    
    category_names = {
        'fc': 'Food Court',
        'library': 'Library',
        'transport': 'Transport',
        'sports': 'Sports',
        'bookdepot': 'Book Depot'
    }
    
    return render_template('domains/incharge/dashboard.html', 
                         feedbacks=feedbacks,
                         category=category,
                         category_name=category_names.get(category, category.title()),
                         total_feedbacks=total_feedbacks,
                         recent_feedbacks=recent_feedbacks,
                         resolved_feedbacks=resolved_feedbacks,
                         timedelta=timedelta)

@incharge_bp.route('/feedback/<int:feedback_id>/resolve', methods=['POST'])
@login_required
def resolve_feedback(feedback_id):
    if not current_user.is_incharge:
        flash('Access denied.', 'danger')
        return redirect(url_for('incharge.login'))
    
    feedback = GeneralFeedback.query.get_or_404(feedback_id)
    
    # Check if this feedback belongs to the incharge's category
    if feedback.category != current_user.incharge_category:
        flash('Access denied.', 'danger')
        return redirect(url_for('incharge.dashboard'))
    
    response = request.form.get('response', '')
    feedback.is_resolved = True
    feedback.admin_response = response
    db.session.commit()
    
    flash('Feedback marked as resolved.', 'success')
    return redirect(url_for('incharge.dashboard'))

@incharge_bp.route('/api/feedback-stats')
@login_required
def feedback_stats():
    if not current_user.is_incharge:
        return jsonify({'error': 'Access denied'}), 403
    
    category = current_user.incharge_category
    
    # Get monthly feedback counts for the last 6 months
    monthly_data = []
    for i in range(6):
        start_date = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
        end_date = start_date.replace(day=28) + timedelta(days=4)
        end_date = end_date - timedelta(days=end_date.day)
        
        count = GeneralFeedback.query.filter_by(category=category).filter(
            GeneralFeedback.timestamp >= start_date,
            GeneralFeedback.timestamp <= end_date
        ).count()
        
        monthly_data.append({
            'month': start_date.strftime('%b %Y'),
            'count': count
        })
    
    return jsonify({'monthly_data': list(reversed(monthly_data))})