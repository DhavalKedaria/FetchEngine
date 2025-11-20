import os
import time
import shutil
import subprocess
import requests
import yt_dlp


def _pick_track(tracks_dict, lang):
    """
    tracks_dict is like:
      {'en': [{'ext':'vtt','url':...}, ...], 'en-US': [...], ...}
    Strategy:
      1) exact lang
      2) base match (e.g., 'en' matches 'en-US')
      3) any available language
    Preference order of ext: srt > vtt > ttml > json3
    """
    pref_ext_order = ['srt', 'vtt', 'ttml', 'json3']

    def best_by_ext(track_list):
        if not track_list:
            return None
        # sort by our preferred ext order
        sorted_list = sorted(
            track_list,
            key=lambda t: pref_ext_order.index(t.get('ext', 'zzzz')) if t.get('ext') in pref_ext_order else 999
        )
        return sorted_list[0]

    # 1) exact
    if lang in tracks_dict and tracks_dict[lang]:
        return lang, best_by_ext(tracks_dict[lang])

    # 2) base match (e.g. 'en' -> any 'en-*')
    for k, v in tracks_dict.items():
        if k.lower().startswith(lang.lower()) and v:
            return k, best_by_ext(v)

    # 3) anything
    for k, v in tracks_dict.items():
        if v:
            return k, best_by_ext(v)

    return None, None


def _download_with_retries(url, dest_path, attempts=4, backoff=0.8, timeout=20):
    last_err = None
    for i in range(attempts):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            if os.path.getsize(dest_path) > 0:
                return True
            last_err = RuntimeError("Empty file")
        except Exception as e:
            last_err = e
        time.sleep(backoff * (2 ** i))
    raise last_err


def _ffmpeg_exists():
    return shutil.which("ffmpeg") is not None


def _vtt_to_srt_ffmpeg(vtt_path, srt_path):
    # Convert via ffmpeg if available
    cmd = ["ffmpeg", "-y", "-i", vtt_path, srt_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def download_subtitles_file(url, out_dir, lang='en', progress_cb=None):
    """
    Returns absolute path to an .srt (if possible) or .vtt file.
    Tries manual subs first, then automatic captions.
    """
    os.makedirs(out_dir, exist_ok=True)

    # minimal opts – just fetch metadata
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'skip_download': True,
        # make networking more resilient
        'retries': 5,
        'fragment_retries': 5,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get('title') or 'subtitle'
    safe_title = "".join(ch for ch in title if ch.isalnum() or ch in " ._-").rstrip()

    # Prefer real subtitles
    subs = info.get('subtitles') or {}
    auto = info.get('automatic_captions') or {}

    # Step 1: try manual subs
    chosen_lang, track = _pick_track(subs, lang)

    # Step 2: fallback to auto-captions
    if not track:
        chosen_lang, track = _pick_track(auto, lang)

    if not track or not track.get('url'):
        return None  # nothing available

    ext = track.get('ext', 'vtt').lower()
    src_url = track['url']

    # Paths
    base_path = os.path.join(out_dir, f"{safe_title}.{chosen_lang or lang}")
    target_ext = 'srt' if ext == 'srt' else 'vtt'
    tmp_path = f"{base_path}.{target_ext}"

    # Progress (optional)
    if progress_cb:
        progress_cb({'status': 'downloading', 'downloaded_bytes': 0, 'total_bytes': 0})

    # Download with retries (avoids "Did not get any data blocks")
    _download_with_retries(src_url, tmp_path)

    # If already SRT, done
    if ext == 'srt':
        return os.path.abspath(tmp_path)

    # If VTT and ffmpeg exists, convert to SRT
    if target_ext == 'vtt' and _ffmpeg_exists():
        srt_path = f"{base_path}.srt"
        ok = _vtt_to_srt_ffmpeg(tmp_path, srt_path)
        if ok and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return os.path.abspath(srt_path)

    # Fallback: return VTT as-is
    return os.path.abspath(tmp_path)
