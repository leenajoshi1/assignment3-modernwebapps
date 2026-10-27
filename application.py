"""Assignment 3 photo portal: Flask, SQLite, and SQLAlchemy."""
import json
import logging
import os
import secrets
from functools import wraps
from pathlib import Path
from flask import Flask, abort, redirect, render_template, request, session, url_for
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
PHOTO_FOLDER = Path(os.getenv("PHOTO_PORTAL_UPLOADS", str(ROOT / "static/images/photos")))
PHOTO_FOLDER.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.getenv("PHOTO_PORTAL_SECRET") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
logging.basicConfig(filename=ROOT / "photoportal.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
Base = declarative_base()
db_name = os.getenv("PHOTO_PORTAL_DB", str(ROOT / "photosdata.db"))
engine = create_engine("sqlite:///" + db_name, connect_args={"check_same_thread": False})
DBSession = sessionmaker(bind=engine)

class PhotoData(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    date_taken = Column(String, default="")
    tags = Column(String, default="")

    def as_dict(self):
        return {"name": self.name, "date_taken": self.date_taken, "tags": self.tags}

Base.metadata.create_all(engine)

def load_photos():
    with DBSession() as db:
        return [p.as_dict() for p in db.query(PhotoData).order_by(PhotoData.id)]

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("user") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

def portal(status=""):
    return render_template("photo-portal.html", photo_list=load_photos(),
                           username=session.get("username", ""),
                           user=session.get("user"), photo_upload_status=status)

# Requirement 2.1: preserve the starter's array of JSON-encoded strings.
@app.get("/photos")
def get_photos():
    response = app.json.response({"photos": [json.dumps(p) for p in load_photos()]})
    response.headers["Cache-Control"] = "no-store"
    return response

# Requirement 2.2
@app.get("/photos/<photo>/tags")
def get_tags_for_photo(photo):
    with DBSession() as db:
        row = db.query(PhotoData).filter_by(name=photo).first()
        response = app.json.response({"tags": (row.tags or "") if row else ""})
        response.headers["Cache-Control"] = "no-store"
        return response

# Requirement 1: check BEFORE saving, with a unique constraint as a second guard.
@app.post("/upload")
@admin_required
def upload_photo():
    file = request.files.get("photo_name")
    name = secure_filename(file.filename or "") if file else ""
    if not name or Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif"}:
        return portal("Please choose a PNG, JPG, JPEG, or GIF photo."), 400
    with DBSession() as db:
        if db.query(PhotoData).filter_by(name=name).first() or (PHOTO_FOLDER / name).exists():
            return portal(f"Photo {name} already exists.")
        row = PhotoData(name=name, date_taken=request.form.get("date_taken", "").strip(),
                        tags=request.form.get("tags", "").strip())
        try:
            db.add(row)
            db.flush()
            # Exclusive creation also prevents concurrent uploads overwriting a file.
            with (PHOTO_FOLDER / name).open("xb") as target:
                file.save(target)
            db.commit()
        except (IntegrityError, FileExistsError):
            db.rollback()
            return portal(f"Photo {name} already exists.")
        except Exception:
            db.rollback()
            (PHOTO_FOLDER / name).unlink(missing_ok=True)
            raise
    app.logger.info("Uploaded photo %s", name)
    return portal(f"Photo {name} uploaded successfully.")

# Requirement 3.3
@app.post("/update_tags")
@admin_required
def update_tags():
    name = request.form.get("photo_name", "")
    with DBSession() as db:
        photo = db.query(PhotoData).filter_by(name=name).first()
        if photo is None:
            return portal(f"Photo {name} does not exist."), 404
        photo.tags = request.form.get("new_tags", "").strip()
        db.commit()
    app.logger.info("Updated tags for %s", name)
    return portal(f"Tags for {name} updated successfully.")

# Requirement 3.4: remove the file as well as its database record.
@app.post("/delete_photos")
@admin_required
def delete_photos():
    name = request.form.get("photo_name", "")
    with DBSession() as db:
        photo = db.query(PhotoData).filter_by(name=name).first()
        if photo is None:
            return portal(f"Photo {name} does not exist."), 404
        (PHOTO_FOLDER / photo.name).unlink(missing_ok=True)
        db.delete(photo)
        db.commit()
    app.logger.info("Deleted photo %s", name)
    return portal(f"Photo {name} deleted successfully.")

@app.post("/login")
def login():
    # Keep the starter's classroom login assumptions (no credential database).
    session.clear()
    session["user"] = "general" if "gmail" in request.form else "admin"
    session["username"] = request.form.get("gmail", request.form.get("username", "")).strip()
    return redirect(url_for("gallery"))

@app.get("/gallery")
def gallery():
    if "username" not in session:
        return redirect(url_for("index"))
    return portal()

@app.post("/logout")
def logout():
    target = "adminindex" if session.get("user") == "admin" else "index"
    session.clear()
    return redirect(url_for(target))

@app.get("/admin")
def adminindex():
    return render_template("adminindex.html")

@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5009)
