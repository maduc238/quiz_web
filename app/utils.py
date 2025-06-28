import os
from werkzeug.utils import secure_filename
import markdown2, bleach
from flask import current_app, flash

def save_image(file_storage):
    if not file_storage or file_storage.filename == "":
        return None       # user không chọn ảnh
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        flash("File type not allowed (png/jpg/jpeg/gif/webp/avif).", "warning")
        return None
    fn = secure_filename(file_storage.filename)
    # tránh đè file: gắn timestamp
    import time, random, string
    stem = f"{int(time.time())}_{''.join(random.choices(string.ascii_lowercase, k=4))}"
    filename = f"{stem}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)
    return f"uploads/{filename}"   # relative to static/


def _delete_file(rel_path):
    """Xoá file trong static/uploads nếu còn tồn tại."""
    if not rel_path:
        return
    path = os.path.join(current_app.static_folder, rel_path)
    try:
        os.remove(path)
    except OSError:
        pass      # file đã xoá trước đó


def md_safe(raw: str | None) -> str:
    html = markdown2.markdown(
        raw or "",
        extras=[
            "break-on-newline",
            "fenced-code-blocks",   # ```python ... ```
            "code-friendly"         # không phá <> trong code inline
        ]
    )

    extra_tags   = {"p", "br", "span", "pre", "code"}
    allowed_tags = bleach.sanitizer.ALLOWED_TAGS | extra_tags

    return bleach.clean(
        html,
        tags=allowed_tags,
        attributes={"span": ["class"], "code": ["class"]},
        strip=True
    )
