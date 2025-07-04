from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from myextensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False,
                              default=generate_password_hash('Srec@123'))
    feedback_responses = db.relationship('FeedbackResponse', backref='student', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Student {self.roll_number}>'

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    warning_message = db.Column(db.Text, default='This feedback is for the specified class only.')
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # New: soft-deletion flag
    is_deleted = db.Column(db.Boolean, default=False)   

    feedback_responses = db.relationship('FeedbackResponse', backref='event', lazy=True)

    def __repr__(self):
        return f'<Event {self.title}>'

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
