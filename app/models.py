from flask_login import UserMixin
from datetime import datetime
from .extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"))
    is_admin = db.Column(db.Boolean, default=False)


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship(
        "Question",
        backref="exam",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Question.order_idx"      # ← thêm dòng này
    )
    max_attempts = db.Column(db.Integer, default=1)  # 0 = unlimited
    class_id = db.Column(db.Integer, db.ForeignKey("class.id"), nullable=True)


class Question(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    text        = db.Column(db.Text, nullable=True)
    image_path  = db.Column(db.String(255))
    exam_id     = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    order_idx   = db.Column(db.Integer, default=0)        # NEW
    options     = db.relationship("Option", backref="question",
                                  cascade="all, delete-orphan", lazy=True)


class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"),
                            nullable=False)
    image_path = db.Column(db.String(255))


class Submission(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    exam_id     = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    score       = db.Column(db.Integer)
    start_time  = db.Column(db.DateTime)
    end_time    = db.Column(db.DateTime)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # quan hệ đã có
    user = db.relationship("User", backref="submissions")
    exam = db.relationship("Exam", backref="submissions")

    # --- thêm dòng này ---
    answers = db.relationship(
        "SubmissionAnswer",
        backref="submission",
        cascade="all, delete-orphan",
        lazy=True
    )


class SubmissionAnswer(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer,
                              db.ForeignKey("submission.id"), nullable=False)
    question_id   = db.Column(db.Integer,
                              db.ForeignKey("question.id"), nullable=False)
    selected_id   = db.Column(db.Integer,  # Option được chọn
                              db.ForeignKey("option.id"), nullable=True)
    is_correct    = db.Column(db.Boolean, default=False)

    question = db.relationship("Question")
    selected = db.relationship("Option", foreign_keys=[selected_id])


class Class(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    students = db.relationship(
        "User", backref="classroom",
        cascade="all, delete-orphan", lazy=True
    )
    exams = db.relationship(
        "Exam", backref="classroom",
        cascade="all, delete-orphan", lazy=True
    )


def attempts_used(exam, user):
    return Submission.query.filter_by(exam=exam, user=user).count()

def attempts_left(exam, user):
    used = attempts_used(exam, user)
    return None if exam.max_attempts == 0 else max(exam.max_attempts - used, 0)
