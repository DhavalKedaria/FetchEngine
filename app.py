from flask import Flask, send_file, render_template, request, jsonify
import os, uuid, tempfile, re
import audio as audio_mod
import video as video_mod
from subtitles import download_subtitles_file
from thumbnails import download_thumbnail_file

app = Flask(__name__)
app.config['DOWNLOAD_DIR'] = os.path.abspath('download')

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/progress/<task_id>')
def progress(task_id):
    data = PROGRESS.get(task_id)
    if not data:
        return jsonify({"pct": 0, "text": "Unknown task", "done": True, "error": "Invalid ID"}), 404
    return jsonify(data)

@app.route('/download_audio', methods=['POST'])
def download_audio():
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
            PROGRESS[task_id].update({"pct": 100, "text": "Done", "done": True})
            return send_file(file_path, as_attachment=True)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Failed to process audio."})
            return "Failed to process the audio. Please try again.", 500

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Audio Download Error: {e}")
        return "An error occurred while processing the audio.", 500

@app.route('/download_video', methods=['POST'])
def download_video():
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
            PROGRESS[task_id].update({"pct": 100, "text": "Done", "done": True})
            return send_file(file_path, as_attachment=True)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Failed to process video."})
            return "Failed to process the video. Please try again.", 500

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Video Download Error: {e}")
        return "An error occurred while processing the video.", 500

@app.route('/download_subtitles', methods=['POST'])
def download_subtitles():
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
            PROGRESS[task_id].update({"pct": 100, "text": "Done", "done": True})
            return send_file(srt_path, as_attachment=True)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Subtitles not available for this language."})
            return "Subtitles not available for this language.", 404

    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Subtitles Error: {e}")
        return "An error occurred while fetching subtitles.", 500

@app.route('/download_thumbnail', methods=['POST'])
def download_thumbnail():
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
            PROGRESS[task_id].update({"pct": 100, "text": "Done", "done": True})
            return send_file(img_path, as_attachment=True)
        else:
            PROGRESS[task_id].update({"done": True, "error": "Thumbnail not found."})
            return "Thumbnail not found.", 404
    except Exception as e:
        PROGRESS[task_id].update({"done": True, "error": str(e)})
        print(f"Thumbnail Error: {e}")
        return "An error occurred while fetching thumbnail.", 500

if __name__ == '__main__':
    os.makedirs(app.config['DOWNLOAD_DIR'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=1500)
