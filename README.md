# quiz_web Online Exam Management System

## Overview

`quiz_web` is a lightweight Flask application that lets teachers create and administer multiple choice tests while students securely sit the exams in a browser.  It grew from a one page demo to a feature complete platform:

* **Markdown + LaTeX** for rich question text and maths formulas
* **Image questions & answers** (any \*.png/\*.jpg/\*.gif)
* Time limited papers with an on screen timer & auto submit
* Attempt quota per exam **per student**
* Classes exams are visible only to enrolled students
* Admin CRUD for exams, questions, classes, users & submissions
* Student dashboard with best‑score history
* SQLite by default, can switch to PostgreSQL/MySQL
* Zero JS frameworks Bootstrap + MathJax only

## Quick start

```bash
# 1. clone and enter
$ git clone https://github.com/your‑org/quiz_web.git && cd quiz_web

# 2. create venv + install deps
$ python -m venv .venv && source .venv/bin/activate
$ pip install -r requirements.txt

# 3. bootstrap DB and create an admin user
$ flask db upgrade           # or python manage.py migrate
$ flask shell <<'PY'
from app import db, User
from werkzeug.security import generate_password_hash
u = User(username="admin", password_hash=generate_password_hash("admin123"), is_admin=True)
db.session.add(u); db.session.commit()
PY

# 4. run
$ flask run -h 0.0.0.0 -p 5000
```

Browse to [http://localhost:5000](http://localhost:5000) and log in with **fil_admin / fil_admin**.

## Architecture

```
quiz_web/
├─ app/
│  ├─ __init__.py       # Flask factory, blueprints
│  ├─ models.py         # SQLAlchemy ORM
│  ├─ admin/            # admin blueprint (CRUD)
│  ├─ student/          # student blueprint (exam flow)
│  ├─ auth/             # unified login/logout routes
│  ├─ utils.py          # helpers (Markdown → HTML, file upload, etc.)
│  └─ templates/        # Jinja2 templates
├─ migrations/          # Flask‑Migrate scripts
├─ static/              # Bootstrap, custom.css, images, timer.js
├─ requirements.txt
└─ manage.py            # CLI entry‑point (optional)
```

### Data model highlight

* **User** ⟶ `is_admin`, `class_id`
* **Class** ⟶ one‑to‑many Users, Exams
* **Exam**  ⟶ owns Questions, `class_id`, `max_attempts`, `duration_minutes`
* **Question** ⟶ four Options, markdown text + optional image, `order_idx`
* **Submission** ⟶ each sit; `score is NULL` while in‑progress
* **SubmissionAnswer** ⟶ chosen option per question

## Feature guide

| Role        | Capability                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------- |
| **Admin**   | create/edit exams, reorder questions, preview, see submissions, delete attempts, manage classes & users |
| **Student** | dashboard of available tests, live timer, auto submit, score + attempt‑left summary, personal history   |

### Markdown / Math

```markdown
**Bold**, *italic*, inline $E=mc^2$, and blocks:
\[
\int_0^\infty e^{-x^2}\,dx=\frac{\sqrt\pi}{2}
\]
```

Rendered by MathJax; code fences `python ... ` are highlighted.

### Security bits

* CSRF via Flask‑WTF (enable in production)
* Upload filtering + `secure_filename`
* Bleach sanitisation on markdown to kill XSS
* Admin cannot delete the last admin user

## Deploy notes (Gunicorn + Nginx)

```bash
# systemd unit snippet
[Service]
ExecStart=/usr/bin/gunicorn -w 4 -b unix:/srv/quiz_web.sock "app:create_app()"
Environment=FLASK_ENV=production
...
```

Serve `/static/` direct from Nginx, hook `proxy_pass` to the socket.

## Contributing

Pull requests welcome!  Please open an issue first to discuss major changes.

### Dev helpers

* `make lint` – run ruff + mypy
* `make test` – pytest suite (SQLite in‑memory)
