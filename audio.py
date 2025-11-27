import yt_dlp
import os
import json
import time

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
        print(f"[audio.py] Warning reading settings: {e}")
    return defaults

def _try_download_with_opts(ydl_opts, url):
    """Helper: run extract_info and return (info, error_str)."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info, None
    except Exception as e:
        return None, str(e)

def getaudio(url, pathname, audio_format='mp3', quality='320', progress_cb=None):
    os.makedirs(pathname, exist_ok=True)
    settings = _load_settings()
    cookies_file = settings.get("COOKIES_FILE")
    cookies_from_browser = settings.get("COOKIES_FROM_BROWSER")
    verbose = bool(settings.get("YT_DLP_VERBOSE"))

    # map codec same as before...
    fmt = audio_format.lower()
    preferredcodec = 'mp3'
    if fmt == 'm4a': preferredcodec = 'm4a'
    elif fmt == 'aac': preferredcodec = 'aac'
    elif fmt == 'ogg': preferredcodec = 'vorbis'
    elif fmt == 'wav': preferredcodec = 'wav'
    elif fmt == 'flac': preferredcodec = 'flac'
    else: preferredcodec = 'mp3'

    base_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'outtmpl': f'{pathname}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': preferredcodec,
            'preferredquality': quality if preferredcodec in ('mp3','aac','vorbis') else None,
        }],
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'quiet': not verbose,
    }

    # Clean up None in postprocessors
    if base_opts['postprocessors'][0].get('preferredquality') is None:
        del base_opts['postprocessors'][0]['preferredquality']

    # 1) If explicit cookies_file exists, prefer it
    if cookies_file:
        cf = os.path.expanduser(cookies_file)
        cf = os.path.abspath(cf)
        if os.path.exists(cf):
            opts = dict(base_opts)
            opts['cookiefile'] = cf
            info, err = _try_download_with_opts(opts, url)
            if info:
                base = yt_dlp.YoutubeDL(opts).prepare_filename(info)  # safe: will not re-download because info exists
                root, _ = os.path.splitext(base)
                final_ext = 'ogg' if preferredcodec == 'vorbis' else preferredcodec
                return os.path.abspath(f"{root}.{final_ext}")
            else:
                print(f"[audio.py] cookiefile download failed: {err}")
        else:
            print(f"[audio.py] cookies file specified but not found: {cf}")

    # 2) Try cookies-from-browser (configured name) and fallbacks
    tried_browsers = []
    if cookies_from_browser:
        # normalize to list
        if isinstance(cookies_from_browser, (list, tuple)):
            browsers = list(cookies_from_browser)
        else:
            browsers = [str(cookies_from_browser)]
    else:
        browsers = []

    # add sensible chromium fallbacks (Edge -> Chrome -> Brave -> Chromium)
    fallbacks = ['edge', 'chrome', 'brave', 'chromium']
    for b in fallbacks:
        if b not in browsers:
            browsers.append(b)

    for browser_name in browsers:
        tried_browsers.append(browser_name)
        opts = dict(base_opts)
        opts['cookiesfrombrowser'] = (browser_name,)
        info, err = _try_download_with_opts(opts, url)
        if info:
            base = yt_dlp.YoutubeDL(opts).prepare_filename(info)
            root, _ = os.path.splitext(base)
            final_ext = 'ogg' if preferredcodec == 'voris' else preferredcodec
            final_ext = 'ogg' if preferredcodec == 'vorbis' else preferredcodec
            return os.path.abspath(f"{root}.{final_ext}")
        else:
            # specific detect common cookie DB copy error to continue trying
            if 'Could not copy Chrome cookie database' in (err or '') or 'Could not copy' in (err or ''):
                print(f"[audio.py] cookiesfrombrowser '{browser_name}' failed, trying next. err={err}")
                continue
            else:
                # other error (e.g., video not available) — stop trying further
                print(f"[audio.py] cookiesfrombrowser '{browser_name}' failed with non-cookie error: {err}")
                return None

    # 3) Last resort: try without cookies
    print(f"[audio.py] Tried browsers {tried_browsers}. Falling back to no-cookies.")
    opts = dict(base_opts)
    info, err = _try_download_with_opts(opts, url)
    if info:
        base = yt_dlp.YoutubeDL(opts).prepare_filename(info)
        root, _ = os.path.splitext(base)
        final_ext = 'ogg' if preferredcodec == 'vorbis' else preferredcodec
        return os.path.abspath(f"{root}.{final_ext}")
    else:
        print(f"[audio.py] Final attempt without cookies failed: {err}")
        return None
