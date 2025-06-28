from flask import (render_template, redirect, url_for, request,
                   flash, abort, current_app)
from flask_login import (login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, desc, asc

from . import admin_bp
from ..extensions import db
from ..models import User, Exam, Question, Option, Submission, SubmissionAnswer, Class
from ..utils import save_image, _delete_file


# ---------- Auth ----------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"],
                                    is_admin=True).first()
        if user and check_password_hash(user.password_hash,
                                        request.form["password"]):
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        flash("Sai tài khoản hoặc không phải admin", "danger")
    return render_template("login.html", is_admin=True)


@admin_bp.route("/login")
def admin_login_redirect():
    return redirect(url_for("auth.login"))


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


# ---------- Dashboard ----------
@admin_bp.route("/")
@login_required
def dashboard():
    if not current_user.is_admin:
        flash("Không đủ quyền", "warning")
        return redirect(url_for("student.index"))
    exams = Exam.query.all()
    return render_template("admin_dashboard.html", exams=exams)


# ---------- CRUD Exam ----------
@admin_bp.route("/exam/new", methods=["GET", "POST"])
@login_required
def new_exam():
    if request.method == "POST":
        exam = Exam(
            title=request.form["title"].strip(),
            duration_minutes=int(request.form["duration"]),
            max_attempts=int(request.form["max_attempts"]),
            class_id=int(request.form["class_id"])
        )
        db.session.add(exam)
        db.session.commit()
        flash("Exam created – tiếp tục thêm câu hỏi", "success")
        return redirect(url_for("admin.edit_exam", exam_id=exam.id))

    # GET: hiển thị form – phải truyền classes
    return render_template("exam_form.html",
                           exam=None,
                           classes=Class.query.order_by(Class.name).all())


@admin_bp.route("/exam/<int:exam_id>/edit", methods=["GET", "POST"])
@login_required
def edit_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)

    if request.method == "POST":
        exam.title = request.form["title"].strip()
        exam.duration_minutes = int(request.form["duration"])
        exam.max_attempts     = int(request.form["max_attempts"])
        exam.class_id         = int(request.form["class_id"])
        db.session.commit()
        flash("Đã lưu thay đổi", "success")

    # luôn truyền classes để dropdown có dữ liệu
    return render_template("exam_form.html",
                           exam=exam,
                           classes=Class.query.order_by(Class.name).all())


@admin_bp.route("/exam/<int:exam_id>/question/new", methods=["POST"])
@login_required
def add_question(exam_id):
    if not current_user.is_admin:
        abort(403)

    exam = Exam.query.get_or_404(exam_id)

    # -------------------- Lấy dữ liệu --------------------
    q_text = request.form.get("question_text", "").strip()
    q_img  = save_image(request.files.get("question_image"))

    # Ít nhất phải có text hoặc ảnh ở câu hỏi
    if not q_text and not q_img:
        flash("Câu hỏi cần text hoặc ảnh.", "warning")
        return redirect(url_for("admin.edit_exam", exam_id=exam.id))

    # order_idx = cuối + 1
    max_idx = db.session.query(db.func.max(Question.order_idx))\
                        .filter_by(exam_id=exam.id).scalar() or 0

    q = Question(text=q_text or "",
                 image_path=q_img,
                 order_idx=max_idx + 1,
                 exam=exam)
    db.session.add(q)

    # -------------------- 4 đáp án --------------------
    has_correct = False
    for i in range(1, 5):
        o_text = request.form.get(f"option_{i}", "").strip()
        o_img  = save_image(request.files.get(f"option_{i}_image"))

        if not o_text and not o_img:
            flash(f"Đáp án {i} thiếu cả text lẫn ảnh.", "warning")
            db.session.rollback()
            return redirect(url_for("admin.edit_exam", exam_id=exam.id))

        is_corr = request.form.get("correct") == str(i)
        has_correct |= is_corr

        db.session.add(Option(
            text=o_text or "",
            image_path=o_img,
            is_correct=is_corr,
            question=q
        ))

    if not has_correct:
        flash("Phải chọn một đáp án đúng.", "warning")
        db.session.rollback()
        return redirect(url_for("admin.edit_exam", exam_id=exam.id))

    db.session.commit()
    flash("Đã thêm câu hỏi.", "success")
    return redirect(url_for("admin.edit_exam", exam_id=exam.id))


@admin_bp.route("/exam/<int:exam_id>/submissions")
@login_required
def view_submissions(exam_id):
    if not current_user.is_admin:
        abort(403)

    sort      = request.args.get("sort", "end_time")   # default = Ended ↓
    direction = request.args.get("dir",  "desc")

    exam = Exam.query.get_or_404(exam_id)

    qry = (Submission.query
           .filter_by(exam=exam)
           .filter(Submission.score.is_not(None)))

    if sort in {"score", "start_time", "end_time"}:
        col   = getattr(Submission, sort)
        order = desc(col) if direction == "desc" else asc(col)
        subs  = qry.order_by(order).all()

    else:  # sort == 'elapsed'
        subs = qry.all()

        def elapsed_sec(s):
            if s.start_time and s.end_time:
                return (s.end_time - s.start_time).total_seconds()
            return -1                              # bản ghi lỗi dữ liệu
        subs.sort(key=elapsed_sec,
                  reverse=(direction == "desc"))

    return render_template("submissions.html",
                           exam=exam,
                           subs=subs,
                           sort=sort,
                           dir=direction)



@admin_bp.route("/question/<int:q_id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(q_id):
    if not current_user.is_admin:
        abort(403)
    q = Question.query.get_or_404(q_id)

    if request.method == "POST":
        q.text = request.form.get("question_text", "").strip()

        # ─── Question image ────────────────────────────────────────
        if "remove_q_image" in request.form:
            _delete_file(q.image_path)          # tuỳ – xoá file vật lý
            q.image_path = None
        new_q_img = save_image(request.files.get("question_image"))
        if new_q_img:
            _delete_file(q.image_path)
            q.image_path = new_q_img

        # ─── Options ───────────────────────────────────────────────
        for idx, opt in enumerate(q.options, start=1):
            opt.text = request.form.get(f"option_{idx}", "").strip()

            # remove?
            if f"remove_option_{idx}_img" in request.form:
                _delete_file(opt.image_path)
                opt.image_path = None

            # upload mới?
            new_img = save_image(request.files.get(f"option_{idx}_image"))
            if new_img:
                _delete_file(opt.image_path)
                opt.image_path = new_img

            opt.is_correct = (request.form.get("correct") == str(idx))

        # ─── Validation: phải còn ít nhất text hoặc ảnh ────────────
        if not q.text and not q.image_path:
            flash("Question must have text or image.", "danger")
            return redirect(request.url)

        for opt in q.options:
            if not opt.text and not opt.image_path:
                flash("Each option must have text or image.", "danger")
                return redirect(request.url)

        db.session.commit()
        flash("Question updated", "success")
        return redirect(url_for("admin.edit_exam", exam_id=q.exam.id))

    return render_template("question_form.html", q=q)


@admin_bp.route("/question/<int:q_id>/delete", methods=["POST"])
@login_required
def delete_question(q_id):
    if not current_user.is_admin:
        abort(403)
    q = Question.query.get_or_404(q_id)
    exam_id = q.exam.id
    db.session.delete(q)
    db.session.commit()
    flash("Question deleted", "info")
    return redirect(url_for("admin.edit_exam", exam_id=exam_id))


@admin_bp.route("/submission/<int:sub_id>/delete", methods=["POST"])
@login_required
def delete_submission(sub_id):
    if not current_user.is_admin:
        abort(403)

    sub = Submission.query.get_or_404(sub_id)
    exam_id = sub.exam_id
    db.session.delete(sub)
    db.session.commit()

    flash("Đã xoá bản ghi kết quả.", "info")
    return redirect(url_for("admin.view_submissions", exam_id=exam_id))


@admin_bp.route("/submission/<int:sub_id>")
@login_required
def view_submission(sub_id):
    if not current_user.is_admin:
        abort(403)
    sub = Submission.query.get_or_404(sub_id)
    answers = SubmissionAnswer.query.filter_by(submission_id=sub.id)\
                                 .order_by(SubmissionAnswer.question_id).all()
    return render_template("submission_detail.html",
                           sub=sub, answers=answers)


@admin_bp.route("/student/new", methods=["GET", "POST"])
@login_required
def create_student():
    if not current_user.is_admin:
        abort(403)

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            flash("Username và password không được rỗng.", "warning")
            return redirect(request.url)

        if User.query.filter_by(username=username).first():
            flash("Username đã tồn tại.", "danger")
            return redirect(request.url)

        user = User(username=username,
                    password_hash=generate_password_hash(password),
                    is_admin=False)
        db.session.add(user)
        db.session.commit()
        flash(f"Tạo student '{username}' thành công.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("student_form.html")


@admin_bp.route("/users")
@login_required
def list_users():
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.id).all()
    return render_template("user_list.html", users=users)


@admin_bp.route("/user/<int:uid>/edit", methods=["GET", "POST"])
@login_required
def edit_user(uid):
    if not current_user.is_admin:
        abort(403)

    user = User() if uid == 0 else User.query.get_or_404(uid)
    is_new = (uid == 0)

    if request.method == "POST":
        # ---------- username ----------
        username = request.form["username"].strip()
        if not username:
            flash("Username không được rỗng.", "warning")
            return redirect(request.url)

        # kiểm tra trùng (ngoại trừ chính user đang sửa)
        q = User.query.filter(func.lower(User.username) == username.lower())
        if not is_new:
            q = q.filter(User.id != user.id)
        if q.first():
            flash("Username đã tồn tại.", "danger")
            return redirect(request.url)

        user.username = username

        # ---------- mật khẩu ----------
        new_pass = request.form.get("password", "").strip()
        if is_new and not new_pass:
            flash("Phải đặt mật khẩu khi tạo user mới.", "warning")
            return redirect(request.url)
        if new_pass:
            user.password_hash = generate_password_hash(new_pass)

        # ---------- quyền ----------
        user.is_admin = ("is_admin" in request.form)

        # ---------- lưu ----------
        db.session.add(user)
        db.session.commit()
        flash("Đã lưu tài khoản." if not is_new else "Đã tạo tài khoản.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("user_form.html", user=user, is_new=is_new)


@admin_bp.route("/user/<int:uid>/delete", methods=["POST"])
@login_required
def delete_user(uid):
    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(uid)

    # Không cho xoá chính mình khi là admin cuối
    if user.is_admin:
        admins = User.query.filter_by(is_admin=True).count()
        if admins <= 1:
            flash("Không thể xoá admin cuối cùng.", "danger")
            return redirect(url_for("admin.list_users"))

    db.session.delete(user)
    db.session.commit()
    flash("Đã xoá tài khoản.", "info")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/question/<int:q_id>/move/<string:direction>", methods=["POST"])
@login_required
def move_question(q_id, direction):
    if not current_user.is_admin:
        abort(403)

    q = Question.query.get_or_404(q_id)
    if direction not in ("up", "down"):
        abort(400)

    # tìm câu kế bên
    neighbor = (Question.query
                .filter_by(exam_id=q.exam_id)
                .filter(Question.order_idx == (q.order_idx - 1 if direction == "up"
                                               else q.order_idx + 1))
                .first())
    if not neighbor:
        return redirect(url_for("admin.edit_exam", exam_id=q.exam_id))

    # hoán đổi chỉ số
    q.order_idx, neighbor.order_idx = neighbor.order_idx, q.order_idx
    db.session.commit()
    return redirect(url_for("admin.edit_exam", exam_id=q.exam_id))


@admin_bp.route("/classes")
@login_required
def list_classes():
    if not current_user.is_admin: abort(403)
    classes = Class.query.order_by(Class.name).all()
    return render_template("class_list.html", classes=classes)


@admin_bp.route("/class/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def edit_class(cid):
    if not current_user.is_admin: abort(403)

    classroom = Class() if cid == 0 else Class.query.get_or_404(cid)
    is_new = cid == 0
    users  = User.query.order_by(User.username).all()

    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Tên lớp không được rỗng.", "warning"); return redirect(request.url)
        classroom.name = name

        # --- gán học sinh ---
        selected_ids = set(map(int, request.form.getlist("students")))
        for u in users:
            u.class_id = classroom.id if u.id in selected_ids else (
                None if u.class_id == classroom.id else u.class_id)

        db.session.add(classroom)
        db.session.commit()
        flash("Đã lưu lớp." if not is_new else "Đã tạo lớp.", "success")
        return redirect(url_for("admin.list_classes"))

    return render_template("class_form.html",
                           classroom=classroom, users=users, is_new=is_new)


@admin_bp.route("/class/<int:cid>/delete", methods=["POST"])
@login_required
def delete_class(cid):
    if not current_user.is_admin: abort(403)
    classroom = Class.query.get_or_404(cid)
    if classroom.exams:
        flash("Không xoá được: lớp còn bài thi.", "danger")
        return redirect(url_for("admin.list_classes"))
    for u in classroom.students:      # huỷ liên kết HS
        u.class_id = None
    db.session.delete(classroom)
    db.session.commit()
    flash("Đã xoá lớp.", "info")
    return redirect(url_for("admin.list_classes"))


@admin_bp.route("/exam/<int:exam_id>/preview")
@login_required
def preview_exam(exam_id):
    if not current_user.is_admin:
        abort(403)

    exam = Exam.query.get_or_404(exam_id)
    # dùng lại template take_exam nhưng truyền cờ read_only
    return render_template("take_exam.html",
                           exam=exam,
                           read_only=True)
