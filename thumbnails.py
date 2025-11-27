# thumbnails.py
import yt_dlp
import os
import json
import requests

_APP_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "appsettings.json")

def _load_settings():
    defaults = {
        "COOKIES_FROM_BROWSER": None,
        "COOKIES_FILE": None,
        "YT_DLP_VERBOSE": False
    }
    try:
        if os.path.exists(_APP_SETTINGS_PATH):
            with open(_APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k in defaults:
                if k in user:
                    defaults[k] = user[k]
    except Exception as e:
        print(f"[thumbnails.py] Warning reading settings: {e}")
    return defaults

def _parse_netscape_cookies(cookiefile_path):
    """
    Very small parser for Netscape-format cookies.txt files.
    Returns dict of {name: value} for top-level domains.
    Ignores comments and empty lines.
    """
    cookies = {}
    try:
        with open(cookiefile_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Netscape format:
                # domain  flag  path  secure  expiration  name  value
                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies[name] = value
                else:
                    # fallback: try simple key=value parsing
                    if '=' in line:
                        try:
                            k, v = line.split('=', 1)
                            cookies[k.strip()] = v.strip()
                        except Exception:
                            continue
    except Exception as e:
        print(f"[thumbnails.py] Failed to parse cookies file: {e}")
    return cookies

def download_thumbnail_file(url, out_dir, progress_cb=None):
    """
    Download best-quality thumbnail for `url` into `out_dir`.
    Returns absolute path to saved thumbnail file, or None on failure.
    Respects appsettings.json for cookies:
      - COOKIES_FILE: path to cookies.txt (preferred)
      - COOKIES_FROM_BROWSER: e.g., "edge", "chrome" (used if COOKIES_FILE missing)
    """
    os.makedirs(out_dir, exist_ok=True)
    settings = _load_settings()
    cookies_file = settings.get("COOKIES_FILE")
    cookies_from_browser = settings.get("COOKIES_FROM_BROWSER")
    verbose = bool(settings.get("YT_DLP_VERBOSE"))

    ydl_opts = {
        'skip_download': True,
        'quiet': not verbose,
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'outtmpl': f'{out_dir}/%(title)s.%(ext)s',
    }

    # Apply cookie options: prefer explicit cookie file
    if cookies_file:
        cf = os.path.expanduser(cookies_file)
        cf = os.path.abspath(cf)
        if os.path.exists(cf):
            ydl_opts['cookiefile'] = cf
        else:
            print(f"[thumbnails.py] cookies file specified but not found: {cf}")
    elif cookies_from_browser:
        # python API expects a tuple for cookiesfrombrowser
        if isinstance(cookies_from_browser, (list, tuple)):
            ydl_opts['cookiesfrombrowser'] = tuple(cookies_from_browser)
        else:
            ydl_opts['cookiesfrombrowser'] = (str(cookies_from_browser),)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"[thumbnails.py] yt-dlp extract_info failed: {e}")
        return None

    title = info.get('title') or 'thumbnail'
    thumbs = info.get('thumbnails') or []
    if not thumbs:
        return None

    # pick the highest-resolution thumbnail
    thumbs_sorted = sorted(thumbs, key=lambda t: t.get('height') or 0, reverse=True)
    best = thumbs_sorted[0]
    thumb_url = best.get('url')
    if not thumb_url:
        return None

    if progress_cb:
        progress_cb({'status': 'downloading', 'downloaded_bytes': 0, 'total_bytes': 0})

    # Prepare cookies for requests if cookie file exists
    req_kwargs = {'stream': True, 'timeout': 20}
    if cookies_file:
        cf = os.path.expanduser(cookies_file)
        cf = os.path.abspath(cf)
        if os.path.exists(cf):
            cookies = _parse_netscape_cookies(cf)
            if cookies:
                req_kwargs['cookies'] = cookies

    try:
        r = requests.get(thumb_url, **req_kwargs)
        r.raise_for_status()
    except Exception as e:
        print(f"[thumbnails.py] Failed to fetch thumbnail URL: {e}")
        return None

    ext = '.jpg'
    ct = r.headers.get('Content-Type', '')
    if 'png' in ct:
        ext = '.png'
    elif 'webp' in ct:
        ext = '.webp'

    safe_title = "".join(ch for ch in title if ch.isalnum() or ch in " ._-").rstrip()
    out_path = os.path.join(out_dir, f"{safe_title}_thumbnail{ext}")

    try:
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"[thumbnails.py] Error writing file: {e}")
        return None

    return os.path.abspath(out_path)
