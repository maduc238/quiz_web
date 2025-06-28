from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from ..models import User
from ..extensions import db, login_manager

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@login_manager.unauthorized_handler
def _redirect_login():
    return redirect(url_for("auth.login", next=request.path))

# ---------- unified login ----------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(
            "admin.dashboard" if current_user.is_admin else "student.index"
        ))

    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash,
                                        request.form["password"]):
            login_user(user)
            # quay về trang họ đang định mở hoặc dashboard
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect(url_for(
                "admin.dashboard" if user.is_admin else "student.index"
            ))
        flash("Sai tài khoản / mật khẩu", "danger")

    return render_template("login.html")


# ---------- logout ----------
@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
