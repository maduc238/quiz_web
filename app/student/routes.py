from datetime import datetime, timedelta
from flask import (render_template, redirect, url_for, request,
                   flash, session)
from flask_login import (login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from dateutil import parser as dtparse

from . import student_bp
from ..extensions import db
from ..models import User, Exam, Option, Submission, SubmissionAnswer, attempts_left


# ---------- Register ----------
# @student_bp.route("/register", methods=["GET", "POST"])
# def register():
#     if request.method == "POST":
#         if User.query.filter_by(username=request.form["username"]).first():
#             flash("Username đã tồn tại", "warning")
#             return redirect(url_for("student.register"))
#         user = User(username=request.form["username"],
#                     password_hash=generate_password_hash(
#                         request.form["password"]))
#         db.session.add(user)
#         db.session.commit()
#         flash("Đăng ký thành công – đăng nhập ngay", "success")
#         return redirect(url_for("student.login"))
#     return render_template("login.html", is_admin=False, register=True)


# ---------- Login / logout ----------
@student_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash,
                                        request.form["password"]):
            login_user(user)
            return redirect(url_for("student.index"))
        flash("Sai tài khoản / mật khẩu", "danger")
    return render_template("login.html", is_admin=False)


@student_bp.route("/login")
def student_login_redirect():
    return redirect(url_for("auth.login"))


@student_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("student.login"))


# ---------- Exam list ----------
@student_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    exams = Exam.query.filter_by(class_id=current_user.class_id).all()

    # ===== attempts còn lại =====
    attempts = {e.id: attempts_left(e, current_user) for e in exams}

    # ===== điểm cao nhất =====
    best = {e.id: "-" for e in exams}         # mặc định chưa thi
    rows = (db.session.query(Submission.exam_id,
                             db.func.max(Submission.score))
            .filter_by(user_id=current_user.id)
            .group_by(Submission.exam_id)
            .all())
    for exam_id, max_score in rows:
        best[exam_id] = max_score           # int

    return render_template("exam_list.html",
                           exams=exams,
                           attempts=attempts,
                           best=best)


# ---------- Take exam ----------
@student_bp.route("/exam/<int:exam_id>/start")
@login_required
def start_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    exam.questions.sort(key=lambda q: q.order_idx)
    
    # 0 = unlimited
    if attempts_left(exam, current_user) == 0:
        flash("Bạn đã hết lượt.", "warning")
        return redirect(url_for("student.index"))

    # đã có phiên chưa nộp? -> tiếp tục
    sub = (Submission.query
           .filter_by(user=current_user, exam=exam, score=None)
           .order_by(Submission.id.desc()).first())

    if not sub:
        sub = Submission(user=current_user,
                         exam=exam,
                         score=None,                     # pending
                         start_time=datetime.utcnow())
        db.session.add(sub)
        db.session.commit()

    session[f"start_{exam_id}"] = sub.start_time.isoformat()
    session[f"sub_id_{exam_id}"] = sub.id                    # nhớ id
    return render_template("take_exam.html", exam=exam)


@student_bp.route("/exam/<int:exam_id>/submit", methods=["POST"])
@login_required
def submit_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)

    # Lấy bản ghi pending
    sub_id = session.pop(f"sub_id_{exam_id}", None)
    sub    = Submission.query.get_or_404(sub_id) if sub_id else None

    # ---------- Tính điểm ----------
    correct = 0
    for q in exam.questions:
        chosen = request.form.get(f"question_{q.id}")
        if chosen and Option.query.get(int(chosen)).is_correct:
            correct += 1
    score = int(100 * correct / len(exam.questions)) if exam.questions else 0

    start_iso = session.pop(f"start_{exam_id}", None)
    start_dt  = dtparse.isoparse(start_iso) if start_iso else datetime.utcnow()
    end_dt    = datetime.utcnow()

    # ---------- Cập nhật bản pending ----------
    if sub and sub.score is None:
        sub.score = score
        sub.end_time = end_dt
    else:
        # Fallback (không nên xảy ra)
        sub = Submission(user=current_user,
                         exam=exam,
                         score=score,
                         start_time=start_dt,
                         end_time=end_dt)
        db.session.add(sub)
        db.session.flush()

    # ---------- Lưu đáp án ----------
    for q in exam.questions:
        chosen_id  = request.form.get(f"question_{q.id}")
        chosen_opt = Option.query.get(int(chosen_id)) if chosen_id else None
        db.session.add(SubmissionAnswer(
            submission_id=sub.id,
            question_id=q.id,
            selected_id=chosen_opt.id if chosen_opt else None,
            is_correct=bool(chosen_opt and chosen_opt.is_correct)
        ))

    db.session.commit()

    elapsed = (end_dt - start_dt).seconds
    return render_template("result.html",
                           score=score,
                           total=len(exam.questions),
                           attempts_left=attempts_left(exam, current_user),
                           elapsed=elapsed)


@student_bp.route("/exam/<int:exam_id>/abort", methods=["POST"])
@login_required
def abort_exam(exam_id):
    sub_id = session.pop(f"sub_id_{exam_id}", None)
    if not sub_id:
        return "", 204

    sub = Submission.query.get(sub_id)
    if sub and sub.score is None:                 # vẫn pending
        sub.score    = 0
        sub.end_time = datetime.utcnow()
        db.session.commit()
    return "", 204


@student_bp.route("/history")
@login_required
def history():
    if current_user.is_admin:      # admin không cần trang này
        return redirect(url_for("admin.dashboard"))

    subs = (Submission.query
            .filter_by(user=current_user)
            .order_by(Submission.end_time.desc())
            .all())

    # Tính thời gian làm
    records = []
    for s in subs:
        elapsed = (s.end_time - s.start_time) if s.end_time and s.start_time else timedelta()
        records.append({
            "exam_title": s.exam.title,
            "score":      s.score,
            "started":    s.start_time,
            "ended":      s.end_time,
            "elapsed":    elapsed
        })

    return render_template("history_list.html", records=records)
