#!/usr/bin/env python3
"""
media_center_app.py

A Flask-based media center app with optional browser downloads or server-only saves
and a tokenized time-limited download endpoint.

Drop into the same folder as your modules:
 - audio.py (with getaudio(...))
 - video.py (with downloader(...))
 - subtitles.py (with download_subtitles_file(...))
 - thumbnails.py (with download_thumbnail_file(...))

Create an appsettings.json alongside this file to configure behavior (example below).
"""

import os
import re
import json
import uuid
import time
import secrets
import threading
from typing import Tuple
from flask import Flask, send_file, render_template, request, jsonify, url_for

# === appsettings.json example (create this file in same folder) ===
# {
#   "ALLOW_BROWSER_DOWNLOADS": false,
#   "DOWNLOAD_DIR": "download",
#   "AUTO_RELOAD_SETTINGS": false,
#   "TOKEN_TTL_SECONDS": 3600,
#   "TOKEN_SINGLE_USE": true,
#   "TOKEN_CLEANUP_INTERVAL": 300
# }
# ===================================================================

APP_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "appsettings.json")

def load_settings():
    # default settings
    base_dir = os.path.abspath(os.path.dirname(__file__))
    defaults = {
        "ALLOW_BROWSER_DOWNLOADS": True,
        "DOWNLOAD_DIR": os.path.join(base_dir, "download"),
        "AUTO_RELOAD_SETTINGS": False,
        "TOKEN_TTL_SECONDS": 3600,
        "TOKEN_SINGLE_USE": True,
        "TOKEN_CLEANUP_INTERVAL": 300   # seconds between cleanup runs
    }
    if os.path.exists(APP_SETTINGS_PATH):
        try:
            with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            # merge only expected keys
            for k in defaults.keys():
                if k in user:
                    # allow relative DOWNLOAD_DIR
                    if k == "DOWNLOAD_DIR":
                        defaults[k] = os.path.abspath(user[k])
                    else:
                        defaults[k] = user[k]
        except Exception as e:
            print(f"[Warning] Failed to read appsettings.json: {e}")
    return defaults

SETTINGS = load_settings()

app = Flask(__name__)
app.config['ALLOW_BROWSER_DOWNLOADS'] = SETTINGS["ALLOW_BROWSER_DOWNLOADS"]
app.config['DOWNLOAD_DIR'] = SETTINGS["DOWNLOAD_DIR"]
app.config['AUTO_RELOAD_SETTINGS'] = SETTINGS["AUTO_RELOAD_SETTINGS"]
app.config['TOKEN_TTL_SECONDS'] = SETTINGS["TOKEN_TTL_SECONDS"]
app.config['TOKEN_SINGLE_USE'] = SETTINGS["TOKEN_SINGLE_USE"]
app.config['TOKEN_CLEANUP_INTERVAL'] = SETTINGS["TOKEN_CLEANUP_INTERVAL"]

# Ensure download dir exists
os.makedirs(app.config['DOWNLOAD_DIR'], exist_ok=True)

# Import your modules (they must be in the same folder or installed)
import audio as audio_mod
import video as video_mod
from subtitles import download_subtitles_file
from thumbnails import download_thumbnail_file

# Simple in-memory progress store: {task_id: {"pct": int, "text": str, "done": bool, "error": str|None}}
PROGRESS = {}

def _new_task():
    task_id = uuid.uuid4().hex
    PROGRESS[task_id] = {"pct": 0, "text": "Starting…", "done": False, "error": None}
    return task_id

def _progress_cb_factory(task_id):
    def cb(d):
        try:
            status = d.get("status")
            if status == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = int(downloaded * 100 / total) if total else 0
                speed = d.get("speed")
                eta = d.get("eta")
                txt = f"Downloading… {pct}%"
                if speed:
                    txt += f" @ {round(speed/1024,1)} KB/s"
                if eta:
                    txt += f", ETA {eta}s"
                PROGRESS[task_id].update({"pct": pct, "text": txt})
            elif status == "finished":
                PROGRESS[task_id].update({"pct": 100, "text": "Processing with ffmpeg…"})
        except Exception:
            # Keep progress resilient
            pass
    return cb

# =================== Token store & helpers ===================
# token -> {"path": str, "filename": str, "expires": float, "used": bool, "single_use": bool}
TOKENS = {}
TOKENS_LOCK = threading.Lock()

def create_token(file_path: str, filename: str = None, ttl: int = None, single_use: bool = None) -> Tuple[str,int]:
    """Create and store a token. Returns (token, ttl)."""
    ttl = ttl if ttl is not None else app.config.get('TOKEN_TTL_SECONDS', 3600)
    single_use = single_use if single_use is not None else app.config.get('TOKEN_SINGLE_USE', True)
    token = secrets.token_urlsafe(24)
    expires_at = time.time() + ttl
    entry = {
        "path": file_path,
        "filename": filename or os.path.basename(file_path),
        "expires": expires_at,
        "used": False,
        "single_use": bool(single_use)
    }
    with TOKENS_LOCK:
        TOKENS[token] = entry
    return token, ttl

def get_token_entry(token: str):
    with TOKENS_LOCK:
        return TOKENS.get(token)

def pop_token(token: str):
    with TOKENS_LOCK:
        return TOKENS.pop(token, None)

def cleanup_tokens_loop():
    """Background thread: remove expired tokens periodically."""
    interval = app.config.get('TOKEN_CLEANUP_INTERVAL', 300)
    while True:
        now = time.time()
        removed = []
        with TOKENS_LOCK:
            for t, entry in list(TOKENS.items()):
                if entry.get("expires", 0) < now or (entry.get("single_use") and entry.get("used")):
                    TOKENS.pop(t, None)
                    removed.append(t)
        # optional: log cleanup
        if removed:
            print(f"[token-cleanup] removed {len(removed)} tokens")
        time.sleep(interval)

# Start cleanup thread as daemon
_cleanup_thread = threading.Thread(target=cleanup_tokens_loop, daemon=True)
_cleanup_thread.start()
# ============================================================

def maybe_reload_settings():
    """Reload settings on every request if AUTO_RELOAD_SETTINGS is true (useful for development)."""
    if app.config.get('AUTO_RELOAD_SETTINGS'):
        s = load_settings()
        app.config['ALLOW_BROWSER_DOWNLOADS'] = s["ALLOW_BROWSER_DOWNLOADS"]
        app.config['DOWNLOAD_DIR'] = s["DOWNLOAD_DIR"]
        app.config['AUTO_RELOAD_SETTINGS'] = s["AUTO_RELOAD_SETTINGS"]
        app.config['TOKEN_TTL_SECONDS'] = s.get("TOKEN_TTL_SECONDS", app.config['TOKEN_TTL_SECONDS'])
        app.config['TOKEN_SINGLE_USE'] = s.get("TOKEN_SINGLE_USE", app.config['TOKEN_SINGLE_USE'])
        app.config['TOKEN_CLEANUP_INTERVAL'] = s.get("TOKEN_CLEANUP_INTERVAL", app.config['TOKEN_CLEANUP_INTERVAL'])

@app.route('/')
def home():
    maybe_reload_settings()
    return render_template('index.html')

@app.route('/progress/<task_id>')
def progress(task_id):
    maybe_reload_settings()
    data = PROGRESS.get(task_id)
    if not data:
        return jsonify({"pct": 0, "text": "Unknown task", "done": True, "error": "Invalid ID"}), 404
    return jsonify(data)

@app.route('/reload_settings', methods=['POST'])
def reload_settings_endpoint():
    """Reload settings from appsettings.json at runtime."""
    s = load_settings()
    app.config['ALLOW_BROWSER_DOWNLOADS'] = s["ALLOW_BROWSER_DOWNLOADS"]
    app.config['DOWNLOAD_DIR'] = s["DOWNLOAD_DIR"]
    app.config['AUTO_RELOAD_SETTINGS'] = s["AUTO_RELOAD_SETTINGS"]
    app.config['TOKEN_TTL_SECONDS'] = s.get("TOKEN_TTL_SECONDS", app.config['TOKEN_TTL_SECONDS'])
    app.config['TOKEN_SINGLE_USE'] = s.get("TOKEN_SINGLE_USE", app.config['TOKEN_SINGLE_USE'])
    app.config['TOKEN_CLEANUP_INTERVAL'] = s.get("TOKEN_CLEANUP_INTERVAL", app.config['TOKEN_CLEANUP_INTERVAL'])
    return jsonify({"reloaded": True, "settings": {
        "ALLOW_BROWSER_DOWNLOADS": app.config['ALLOW_BROWSER_DOWNLOADS'],
        "DOWNLOAD_DIR": app.config['DOWNLOAD_DIR'],
        "AUTO_RELOAD_SETTINGS": app.config['AUTO_RELOAD_SETTINGS'],
        "TOKEN_TTL_SECONDS": app.config['TOKEN_TTL_SECONDS'],
        "TOKEN_SINGLE_USE": app.config['TOKEN_SINGLE_USE']
    }})

# Tokenized download endpoint
@app.route('/token_download/<token>', methods=['GET'])
def token_download(token):
    maybe_reload_settings()
    entry = get_token_entry(token)
    if not entry:
        return "Invalid or expired token", 404

    # check expiry
    if time.time() > entry["expires"]:
        pop_token(token)
        return "Token expired", 410

    # single-use enforced?
    if entry.get("single_use") and entry.get("used"):
        pop_token(token)
        return "Token already used", 410

    file_path = entry.get("path")
    if not file_path or not os.path.exists(file_path):
        pop_token(token)
        return "File not found", 404

    # mark used if single-use
    if entry.get("single_use"):
        with TOKENS_LOCK:
            if token in TOKENS:
                TOKENS[token]["used"] = True

    # Send file as attachment — allowed because this endpoint is explicitly for download by token
    return send_file(file_path, as_attachment=True, download_name=entry.get("filename"))

def _return_or_report_file(file_path, task_id, suggested_name=None):
    """
    If browser downloads are allowed, send the file as attachment.
    Otherwise return JSON with a tokenized download URL (no attachment).
    """
    app_allow = app.config.get('ALLOW_BROWSER_DOWNLOADS', True)
    PROGRESS[task_id].update({"pct": 100, "text": "Done", "done": True})
    if app_allow:
        # browser download directly
        return send_file(file_path, as_attachment=True, download_name=suggested_name)
    else:
        # only save on server — return JSON with token+download URL (no attachment)
        token_ttl = app.config.get('TOKEN_TTL_SECONDS', 3600)
        token_single = app.config.get('TOKEN_SINGLE_USE', True)
        token, ttl = create_token(file_path, filename=suggested_name or os.path.basename(file_path),
                                  ttl=token_ttl, single_use=token_single)
        try:
            download_url = url_for('token_download', token=token, _external=True)
        except RuntimeError:
            # If url_for fails (no request context), fallback to relative url
            download_url = f"/token_download/{token}"
        # Return JSON (use jsonify so proper Content-Type header prevents browser "save JSON" behavior)
        return jsonify({
            "saved": True,
            "download_dir": app.config['DOWNLOAD_DIR'],
            "relative_path": os.path.relpath(file_path, start=app.config['DOWNLOAD_DIR']),
            "filename": suggested_name or os.path.basename(file_path),
            "token": token,
            "download_url": download_url,
            "expires_in": ttl
        }), 200

# === Endpoints (audio/video/subtitles/thumbnail) ===

@app.route('/download_audio', methods=['POST'])
def download_audio():
    maybe_reload_settings()
    url = request.form.get('url')
    fmt = (request.form.get('audio_format') or 'mp3').lower()
    task_id = request.form.get('task_id') or _new_task()

    if not url:
        return "No URL provided!", 400
    if task_id not in PROGRESS:
        PROGRESS[task_id] = {"pct": 0, "text": "Starting…", "done": False, "error": None}

    try:
        out_dir = app.config['DOWNLOAD_DIR']
        os.makedirs(out_dir, exist_ok=True)
        file_path = audio_mod.getaudio(
            url=url,
            pathname=out_dir,
            audio_format=fmt,
            quality='320',
            progress_cb=_progress_cb_factory(task_id)
        )

        if file_path and os.path.exists(file_path):
            suggested_name = os.path.basename(file_path)
            return _return_or_report_file(file_path, task_id, suggested_name)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Failed to process audio."})
            return "Failed to process the audio. Please try again.", 500

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Audio Download Error: {e}")
        return "An error occurred while processing the audio.", 500

@app.route('/download_video', methods=['POST'])
def download_video():
    maybe_reload_settings()
    video_url = request.form.get('video_url')
    resolution = request.form.get('resolution', '720')
    vid_format = (request.form.get('format') or 'mp4').lower()
    task_id = request.form.get('task_id') or _new_task()

    if not video_url:
        return "No video URL provided!", 400
    if task_id not in PROGRESS:
        PROGRESS[task_id] = {"pct": 0, "text": "Starting…", "done": False, "error": None}

    try:
        out_dir = app.config['DOWNLOAD_DIR']
        os.makedirs(out_dir, exist_ok=True)
        file_path = video_mod.downloader(
            url=video_url,
            output_folder=out_dir,
            fmt=vid_format,
            resolution=int(re.sub(r'\D', '', str(resolution)) or '720'),
            progress_cb=_progress_cb_factory(task_id)
        )

        if file_path and os.path.exists(file_path):
            suggested_name = os.path.basename(file_path)
            return _return_or_report_file(file_path, task_id, suggested_name)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Failed to process video."})
            return "Failed to process the video. Please try again.", 500

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Video Download Error: {e}")
        return "An error occurred while processing the video.", 500

@app.route('/download_subtitles', methods=['POST'])
def download_subtitles():
    maybe_reload_settings()
    url = request.form.get('subs_url')
    lang = (request.form.get('subs_lang') or 'en').lower()
    task_id = request.form.get('task_id') or _new_task()

    if not url:
        return "No URL provided!", 400
    if task_id not in PROGRESS:
        PROGRESS[task_id] = {"pct": 0, "text": "Starting…", "done": False, "error": None}

    try:
        out_dir = app.config['DOWNLOAD_DIR']
        os.makedirs(out_dir, exist_ok=True)
        PROGRESS[task_id].update({"pct": 10, "text": f"Fetching subtitles ({lang})…"})

        srt_path = download_subtitles_file(url, out_dir, lang, progress_cb=_progress_cb_factory(task_id))
        if srt_path and os.path.exists(srt_path):
            return _return_or_report_file(srt_path, task_id, suggested_name=os.path.basename(srt_path))
        else:
            PROGRESS[task_id].update({"done": True, "error": "Subtitles not available for this language."})
            return "Subtitles not available for this language.", 404

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Subtitles Error: {e}")
        return "An error occurred while fetching subtitles.", 500

@app.route('/download_thumbnail', methods=['POST'])
def download_thumbnail():
    maybe_reload_settings()
    url = request.form.get('thumb_url')
    task_id = request.form.get('task_id') or _new_task()

    if not url:
        return "No URL provided!", 400
    if task_id not in PROGRESS:
        PROGRESS[task_id] = {"pct": 0, "text": "Starting…", "done": False, "error": None}

    try:
        out_dir = app.config['DOWNLOAD_DIR']
        os.makedirs(out_dir, exist_ok=True)
        PROGRESS[task_id].update({"pct": 10, "text": "Fetching metadata…"})
        img_path = download_thumbnail_file(url, out_dir, progress_cb=_progress_cb_factory(task_id))
        if img_path and os.path.exists(img_path):
            return _return_or_report_file(img_path, task_id, suggested_name=os.path.basename(img_path))
        else:
            PROGRESS[task_id].update({"done": True, "error": "Thumbnail not found."})
            return "Thumbnail not found.", 404
    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Thumbnail Error: {e}")
        return "An error occurred while fetching thumbnail.", 500

# === Run app ===
if __name__ == '__main__':
    # Ensure download dir exists
    os.makedirs(app.config['DOWNLOAD_DIR'], exist_ok=True)
    # run
    app.run(debug=True, host='0.0.0.0', port=1600)
