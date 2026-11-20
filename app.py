"""Local lesson UI and progress storage. Learner code runs in the browser."""
import io
import json
import os
import secrets
import sys
import threading
import tempfile
from functools import wraps
from pathlib import Path
import time
import webbrowser

# In windowed (no-console) PyInstaller builds, sys.stdout/stderr are None, so
# any print() would crash. Give them a harmless sink first.
if getattr(sys, "stdout", None) is None:
    sys.stdout = io.StringIO()
if getattr(sys, "stderr", None) is None:
    sys.stderr = io.StringIO()

# Windows consoles default to cp1252, which crashes on the emoji we print.
# Force UTF-8 so startup banners (and any stray emoji) never raise.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from flask import Flask, jsonify, render_template, request, send_from_directory

from lessons import loader
from browser_runner import start_runner

# ---------------------------------------------------------------------------
# Path handling — works both as a plain script and as a PyInstaller bundle.
# When frozen, data files live under sys._MEIPASS; writable files (progress)
# must live next to the executable so they survive and are user-visible.
# ---------------------------------------------------------------------------
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    BUNDLE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
    APP_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BUNDLE_DIR

PROGRESS_PATH = os.path.join(APP_DIR, "progress.json")
PROGRESS_VERSION = 2

# Per-launch token: protects state-changing endpoints from other tabs/websites.
LAUNCH_TOKEN = secrets.token_hex(16)

MAX_CODE_CHARS = 100_000
MAX_STDIN_CHARS = 10_000

app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024  # 256 KB request cap


UI_ORIGIN = "http://127.0.0.1:5001"
RUNNER_ORIGIN = ""
PROGRESS_LOCK = threading.RLock()


@app.before_request
def _guard_request():
    if request.host != UI_ORIGIN.removeprefix("http://"):
        return jsonify(error="This app only accepts its local address."), 403
    if request.path.startswith("/api/"):
        if request.headers.get("X-Tutor-Token") != LAUNCH_TOKEN:
            return jsonify(error="Session token mismatch. Refresh the page."), 401
        origin = request.headers.get("Origin")
        if origin is not None and origin != UI_ORIGIN:
            return jsonify(error="This request came from another site."), 403


@app.after_request
def _headers(response):
    frames = RUNNER_ORIGIN or "'none'"
    response.headers.update({
        "Content-Security-Policy": (
            "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            f"frame-src {frames}; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        ),
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store",
    })
    return response


def progress_transaction(handler):
    @wraps(handler)
    def locked(*args, **kwargs):
        with PROGRESS_LOCK:
            return handler(*args, **kwargs)
    return locked


# ---------------------------------------------------------------------------
# Progress persistence (safe atomic writes + migration)
# ---------------------------------------------------------------------------
def _default_progress():
    return {"version": PROGRESS_VERSION, "xp": 0, "completed": [],
            "last_opened": None, "lessons": {}}


def _migrate(data):
    """Upgrade older progress files without losing any learner data."""
    if not isinstance(data, dict):
        return _default_progress()
    migrated = _default_progress()
    try:
        migrated["xp"] = int(data.get("xp", 0) or 0)
    except (TypeError, ValueError):
        migrated["xp"] = 0
    completed = data.get("completed")
    if isinstance(completed, list):
        try:
            migrated["completed"] = [int(x) for x in completed]
        except (TypeError, ValueError):
            migrated["completed"] = []
    lessons = data.get("lessons")
    if isinstance(lessons, dict):
        for key, value in lessons.items():
            if isinstance(value, dict) and ("code" in value or "stdin" in value):
                migrated["lessons"][str(key)] = {
                    "code": str(value.get("code", "")),
                    "stdin": str(value.get("stdin", "")),
                }
    last = data.get("last_opened")
    migrated["last_opened"] = int(last) if isinstance(last, int) else None
    return migrated


def _read_progress():
    try:
        with open(PROGRESS_PATH, "r", encoding="utf-8") as fh:
            return _migrate(json.load(fh))
    except FileNotFoundError:
        return _default_progress()
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        backup = PROGRESS_PATH + "." + secrets.token_hex(6) + ".corrupt"
        try:
            os.replace(PROGRESS_PATH, backup)
            print(f"[progress] unreadable progress file moved to {backup}: {exc}")
        except OSError:
            print(f"[progress] unreadable progress file: {exc}")
        return _default_progress()


def _write_progress(data):
    """Atomically write progress (temp file + rename). Returns (ok, message)."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                         prefix="progress-", suffix=".tmp",
                                         dir=Path(PROGRESS_PATH).parent) as fh:
            tmp_path = fh.name
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, PROGRESS_PATH)
        return True, "saved"
    except OSError as exc:
        print(f"[progress] could not save: {exc}")
        return False, (
            "Saving failed — your latest changes may not be kept. Check that "
            "this folder isn't read-only and there's disk space, then try again."
        )

    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


def _save_lesson_work(progress, lesson_id, code, stdin):
    progress["lessons"] = progress.get("lessons") or {}
    progress["lessons"][str(lesson_id)] = {"code": code, "stdin": stdin}
    progress["last_opened"] = int(lesson_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    # The per-launch token is rendered into the page; the front-end sends it
    # back as the X-Tutor-Token header on every state-changing request.
    return render_template("index.html", token=LAUNCH_TOKEN, runner_origin=RUNNER_ORIGIN)


@app.route("/api/lessons")
@progress_transaction
def api_lessons():
    progress = _read_progress()
    return jsonify({
        "lessons": loader.load_summaries(),
        "progress": progress,
        "last_opened": progress.get("last_opened"),
        "python_ready": bool(RUNNER_ORIGIN),
    })


@app.route("/api/lessons/<int:lesson_id>")
@progress_transaction
def api_lesson(lesson_id):
    lesson = loader.load_one(lesson_id)
    if lesson is None:
        return jsonify({"error": "Lesson not found"}), 404
    # Include this lesson's saved work (if any) so the front-end can restore it.
    saved = (_read_progress().get("lessons") or {}).get(str(lesson_id))
    lesson["saved"] = saved
    return jsonify(lesson)


def _valid_code_payload(body):
    code = body.get("code", "")
    stdin_data = body.get("stdin", "")
    if not isinstance(code, str) or not isinstance(stdin_data, str):
        return None, None, "Code and input must be text."
    if len(code) > MAX_CODE_CHARS or len(stdin_data) > MAX_STDIN_CHARS:
        return None, None, "That's a lot of code — it's bigger than we can handle."
    return code, stdin_data, None


@app.post("/api/complete")
@progress_transaction
def api_complete():
    # Browser challenge checks provide practice feedback. XP is local and self-reported.
    body = request.get_json(silent=True)
    lesson_id = body.get("lesson_id") if isinstance(body, dict) else None
    if type(lesson_id) is not int:
        return jsonify(error="Choose a lesson."), 400
    lesson = loader.load_one(lesson_id)
    if lesson is None:
        return jsonify(error="Lesson not found."), 404
    progress = _read_progress()
    if lesson_id in progress["completed"]:
        return jsonify(xp_awarded=0, progress=progress)
    xp = int(lesson.get("xp", 50))
    progress["completed"].append(lesson_id)
    progress["xp"] += xp
    ok, message = _write_progress(progress)
    if not ok:
        return jsonify(xp_awarded=0, progress=_read_progress(), save_error=message)
    return jsonify(xp_awarded=xp, progress=progress)


@app.route("/api/save", methods=["POST"])
@progress_transaction
def api_save():
    """Autosave a lesson's code + input. Returns a visible save state."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or type(body.get("lesson_id")) is not int:
        return jsonify(ok=False, state="error", message="Invalid lesson or save data."), 400
    lesson_id = body["lesson_id"]
    code, stdin_data, err = _valid_code_payload(body)
    if err:
        return jsonify({"ok": False, "state": "error", "message": err}), 400
    if lesson_id is None or loader.load_one(int(lesson_id)) is None:
        return jsonify({"ok": False, "state": "error", "message": "Unknown lesson."}), 404
    progress = _read_progress()
    _save_lesson_work(progress, int(lesson_id), code, stdin_data)
    ok, message = _write_progress(progress)
    return jsonify({"ok": ok, "state": "saved" if ok else "error", "message": message})


@app.get("/api/progress")
@progress_transaction
def api_progress():
    return jsonify(_read_progress())


@app.post("/api/progress/reset")
@progress_transaction
def api_reset():
    progress = _read_progress()
    progress.update(xp=0, completed=[])
    ok, message = _write_progress(progress)
    return jsonify(ok=ok, message=message)


@app.post("/api/progress/erase")
@progress_transaction
def api_erase():
    try:
        root = Path(PROGRESS_PATH)
        for path in [*root.parent.glob(root.name + ".*.corrupt"), root.with_suffix(".json.corrupt"), root]:
            path.unlink(missing_ok=True)
    except OSError:
        return jsonify(ok=False, message="Some saved work could not be erased."), 500
    return jsonify(ok=True)


@app.route("/api/quit", methods=["POST"])
def api_quit():
    """Shut the app down. With the console hidden there's no window to close,
    so the UI's Quit button calls this. We exit the whole process shortly after
    responding so the browser gets a clean acknowledgement first."""
    def _die():
        time.sleep(0.4)
        os._exit(0)
    threading.Thread(target=_die, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.svg",
                               mimetype="image/svg+xml")


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    port = int(os.environ.get("TUTOR_PORT", "5001"))
    host = os.environ.get("TUTOR_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("PyDocent must run on 127.0.0.1 or localhost; remote code execution is not supported.")
    global UI_ORIGIN, RUNNER_ORIGIN
    UI_ORIGIN = url = f"http://127.0.0.1:{port}"
    RUNNER_ORIGIN = start_runner(BUNDLE_DIR, UI_ORIGIN)
    # Auto-open the browser unless suppressed (set TUTOR_NO_BROWSER=1 for tests).
    if os.environ.get("TUTOR_NO_BROWSER") != "1":
        threading.Timer(1.0, _open_browser, args=[url]).start()
    print(f"\n  🐍 PyDocent is running at {url}")
    print("  (Close this window to stop the app.)\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
