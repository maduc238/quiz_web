from flask import Flask
from .extensions import db, login_manager
from .models import User
from .utils import md_safe


def create_app():
    app = Flask(__name__)
    from config import Config
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # blueprints
    from .admin.routes import admin_bp
    from .student.routes import student_bp
    from .auth.routes import auth_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(student_bp)          # root='/'
    app.register_blueprint(auth_bp)

    app.jinja_env.filters["md"] = md_safe

    with app.app_context():
        db.create_all()

        admin_username = "fil_admin"
        admin_password = "fil_admin"
        # seed default admin nếu chưa có
        if not User.query.filter_by(username=admin_username).first():
            from werkzeug.security import generate_password_hash
            admin = User(username=admin_username,
                         password_hash=generate_password_hash(admin_password),
                         is_admin=True)
            db.session.add(admin)
            db.session.commit()

    return app
