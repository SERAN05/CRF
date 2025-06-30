import os
from flask import Flask, render_template
from flask_migrate import Migrate
from config import Config
from myextensions import db, login_manager

migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'admin.login'
    login_manager.login_message_category = 'info'

    from routes.admin_routes import admin_bp
    from routes.student_routes import student_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)

    with app.app_context():
        from models import User, Student, Event, Course, Staff, Question, FeedbackResponse
        db.create_all()

        # Create admin and default questions if not present
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(username='admin', 
                         password_hash=generate_password_hash('admin123'),
                         is_admin=True)
            db.session.add(admin)
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
            for i, q_text in enumerate(questions_text, start=1):
                from models import Question
                db.session.add(Question(id=i, text=q_text))
            db.session.commit()

    @app.route('/')
    def index():
        return render_template('base.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
