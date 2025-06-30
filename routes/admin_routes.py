import os
import pandas as pd
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, inspect
from myextensions import db

from models import User, Student, Event, Course, Staff, Question, FeedbackResponse, QuestionResponse
from utils.excel_handler import allowed_file, validate_student_excel
from utils.pdf_generator import generate_pdf_report

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Helper function: applies filter_by(is_deleted=False) if the table has an is_deleted column.
def safe_filter(query_obj):
    try:
        # Get the entity (model) from the query.
        entity = query_obj.column_descriptions[0]['entity']
        # Use SQLAlchemy inspector to check column names.
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(entity.__tablename__)]
        if 'is_deleted' in columns:
            return query_obj.filter_by(is_deleted=False)
    except Exception:
        # In case of any error, simply return the original query.
        pass
    return query_obj

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_admin:
            login_user(user, remember=False)
            flash("Logged in successfully", "success")
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to view this page.', 'danger')
        return redirect(url_for('admin.login'))
    # Use safe_filter so that if is_deleted column is not present, we fall back to all events.
    events = safe_filter(Event.query).all()
    courses = Course.query.all()
    total_students = Student.query.count()
    total_responses = FeedbackResponse.query.count()
    active_event = safe_filter(Event.query.filter_by(is_active=True)).first()
    completion_rate = 0
    if total_students > 0 and active_event:
        event_responses = FeedbackResponse.query.filter_by(event_id=active_event.id).count()
        completion_rate = (event_responses / total_students) * 100
    return render_template('admin/dashboard.html', events=events, courses=courses,
                           total_students=total_students, total_responses=total_responses,
                           active_event=active_event, completion_rate=completion_rate)

@admin_bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin.', 'danger')
        return redirect(url_for('admin.login'))
    # Import Question at the beginning to avoid UnboundLocalError.
    from models import Question
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            title = request.form.get('title')
            description = request.form.get('description')
            additional_questions = request.form.get('additional_questions')
            warning_message = request.form.get('warning_message')
            if not title:
                flash('Event title is required', 'danger')
                return redirect(url_for('admin.manage_events'))
            event = Event(title=title, description=description, warning_message=warning_message, is_active=False)
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
            if request.form.get('is_active') == 'true':
                event.is_active = True
            db.session.commit()
            flash(f'Event "{event.title}" status updated', 'success')
        elif action == 'delete':
            event_id = request.form.get('event_id')
            event = Event.query.get_or_404(event_id)
            event.is_deleted = True
            db.session.commit()
            flash('Event was moved to Past Responses.', 'success')
    events = safe_filter(Event.query).all()
    questions = Question.query.all()
    return render_template('admin/manage_events.html', events=events, questions=questions)

@admin_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    q = Question.query.get_or_404(question_id)
    if q.responses:
        flash("Cannot delete question with existing responses.", "danger")
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
    return render_template('admin/past_responses.html', past_events=past_events)

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
            staff = Staff(name=staff_name, course_id=course_id)
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
    courses = Course.query.all()
    return render_template('admin/manage_courses.html', courses=courses)

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
                    for roll_number, name in students_data:
                        existing_student = Student.query.filter_by(roll_number=roll_number).first()
                        if existing_student:
                            existing_student.name = name
                        else:
                            new_student = Student(
                                roll_number=roll_number,
                                name=name,
                                password_hash=generate_password_hash('Srec@123')
                            )
                            db.session.add(new_student)
                    db.session.commit()
                    flash(f'Successfully processed {len(students_data)} students', 'success')
                except Exception as e:
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
                password_hash=generate_password_hash('Srec@123')
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
            count_skipped = 0
            for s in students:
                if FeedbackResponse.query.filter_by(student_id=s.id).count() == 0:
                    db.session.delete(s)
                    count_deleted += 1
                else:
                    count_skipped += 1
            db.session.commit()
            flash(f"Deleted {count_deleted} students. {count_skipped} not deleted (existing responses).", "success")
    students = Student.query.all()
    return render_template('admin/manage_students.html', students=students)

@admin_bp.route('/results')
@login_required
def results():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.login'))
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    courses = Course.query.all()
    staffs = Staff.query.all()
    questions = Question.query.all()
    return render_template('admin/results.html', active_event=active_event,
                           courses=courses, staffs=staffs, questions=questions)

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
    feedback_responses = FeedbackResponse.query.filter_by(staff_id=staff_id, event_id=event_id).all()
    question_averages = {}
    questions = Question.query.all()
    for q in questions:
        ratings = []
        for feedback in feedback_responses:
            resp = QuestionResponse.query.filter_by(feedback_id=feedback.id, question_id=q.id).first()
            if resp:
                ratings.append(resp.rating)
        if ratings:
            avg = sum(ratings) / len(ratings)
            question_averages[q.id] = {'question_text': q.text, 'average': round(avg, 2), 'count': len(ratings)}
        else:
            question_averages[q.id] = {'question_text': q.text, 'average': 0, 'count': 0}
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
    pdf_buffer = generate_pdf_report(staff_id, event_id)
    staff = Staff.query.get_or_404(staff_id)
    event = Event.query.get_or_404(event_id)
    filename = f"report_{staff.course.code}_{staff.name.replace(' ', '_')}_{event.title.replace(' ', '_')}.pdf"
    return send_file(BytesIO(pdf_buffer.getvalue()), mimetype='application/pdf',
                     as_attachment=True, download_name=filename)
