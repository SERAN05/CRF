from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from myextensions import db
from models import Student, Event, FeedbackResponse, Course, Staff, Question, QuestionResponse

student_bp = Blueprint('student', __name__, url_prefix='/student')

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
            session['student_id'] = student.id
            flash("Logged in successfully", "success")
            return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('student/login.html')

@student_bp.route('/logout')
def logout():
    session.pop('student_id', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('student.login'))

@student_bp.route('/dashboard')
def dashboard():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    student = Student.query.get_or_404(student_id)
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    has_submitted = False
    if active_event:
        existing_feedback = FeedbackResponse.query.filter_by(student_id=student_id, event_id=active_event.id).first()
        if existing_feedback:
            has_submitted = True
    return render_template('student/dashboard.html', 
                           student=student,
                           active_event=active_event,
                           has_submitted=has_submitted)

@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback_form():
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))
    student = Student.query.get_or_404(student_id)
    try:
        active_event = Event.query.filter_by(is_active=True, is_deleted=False).first()
    except Exception:
        active_event = Event.query.filter_by(is_active=True).first()
    if not active_event:
        flash('No active feedback event available', 'warning')
        return redirect(url_for('student.dashboard'))
    existing_feedback = FeedbackResponse.query.filter_by(student_id=student_id, event_id=active_event.id).first()
    if existing_feedback:
        flash('You have already submitted feedback for this event', 'warning')
        return redirect(url_for('student.dashboard'))
    if request.method == 'POST':
        courses_data = {}
        courses = Course.query.all()
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
    courses = Course.query.all()
    questions = Question.query.all()
    course_staffs = {}
    for course in courses:
        course_staffs[course.id] = Staff.query.filter_by(course_id=course.id).all()
    return render_template('student/feedback_form.html',
                           student=student,
                           event=active_event,
                           courses=courses,
                           questions=questions,
                           course_staffs=course_staffs)

@student_bp.route('/thank-you')
def thank_you():
    if not session.get('student_id'):
        return redirect(url_for('student.login'))
    return render_template('student/thank_you.html')
