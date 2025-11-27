# video.py
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
        print(f"[video.py] Warning reading settings: {e}")
    return defaults

def _try_download_with_opts(ydl_opts, url):
    """Run extract_info once with given options. Returns (info, error_str)."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info, None
    except Exception as e:
        return None, str(e)

def downloader(url, output_folder, fmt='mp4', resolution=1080, progress_cb=None):
    """
    Download video from `url` into `output_folder` with requested container `fmt`
    and target `resolution` (height). Supports cookies via appsettings.json.

    Returns absolute path to final file on success, or None on error.
    """
    os.makedirs(output_folder, exist_ok=True)
    settings = _load_settings()
    cookies_file = settings.get("COOKIES_FILE")
    cookies_from_browser = settings.get("COOKIES_FROM_BROWSER")
    verbose = bool(settings.get("YT_DLP_VERBOSE"))

    merge_format = fmt.lower() if fmt.lower() in ('mp4', 'webm', 'mkv') else 'mp4'

    base_opts = {
        'format': f'bestvideo[height<={int(resolution)}]+bestaudio/best',
        'merge_output_format': merge_format,
        'outtmpl': f'{output_folder}/%(title)s.%(ext)s',
        'concurrent_fragment_downloads': 4,
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'quiet': not verbose,
        # use the (misspelled) 'preferedformat' key expected by yt-dlp's postprocessor class
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': merge_format,
        }],
    }

    # Remove None fields in postprocessor if present
    pp = base_opts.get('postprocessors', [])
    if pp and pp[0].get('preferedformat') is None:
        del pp[0]['preferedformat']

    # 1) If explicit cookies_file exists, try it first
    if cookies_file:
        cf = os.path.expanduser(cookies_file)
        cf = os.path.abspath(cf)
        if os.path.exists(cf):
            opts = dict(base_opts)
            opts['cookiefile'] = cf
            info, err = _try_download_with_opts(opts, url)
            if info:
                # prepare filename from info
                with yt_dlp.YoutubeDL(opts) as ydl_tmp:
                    file_path = ydl_tmp.prepare_filename(info)
                root, _ = os.path.splitext(file_path)
                final = f"{root}.{merge_format}"
                return os.path.abspath(final)
            else:
                print(f"[video.py] cookiefile download failed: {err}")
        else:
            print(f"[video.py] cookies file specified but not found: {cf}")

    # 2) Try cookies-from-browser with fallbacks
    tried_browsers = []
    if cookies_from_browser:
        # normalize to list
        if isinstance(cookies_from_browser, (list, tuple)):
            browsers = list(cookies_from_browser)
        else:
            browsers = [str(cookies_from_browser)]
    else:
        browsers = []

    # ensure common chromium fallbacks are present (edge -> chrome -> brave -> chromium)
    fallbacks = ['edge', 'chrome', 'brave', 'chromium']
    for b in fallbacks:
        if b not in browsers:
            browsers.append(b)

    for browser_name in browsers:
        tried_browsers.append(browser_name)
        opts = dict(base_opts)
        # cookiesfrombrowser requires a tuple for the python API
        opts['cookiesfrombrowser'] = (browser_name,)
        info, err = _try_download_with_opts(opts, url)
        if info:
            with yt_dlp.YoutubeDL(opts) as ydl_tmp:
                file_path = ydl_tmp.prepare_filename(info)
            root, _ = os.path.splitext(file_path)
            final = f"{root}.{merge_format}"
            return os.path.abspath(final)
        else:
            # If the error looks like cookie DB copy failure, continue to next browser
            if 'Could not copy Chrome cookie database' in (err or '') or 'Could not copy' in (err or ''):
                print(f"[video.py] cookiesfrombrowser '{browser_name}' failed (DB copy issue), trying next. err={err}")
                continue
            else:
                # Non-cookie error (like video restricted/unavailable); stop and return None
                print(f"[video.py] cookiesfrombrowser '{browser_name}' failed: {err}")
                return None

    # 3) Last resort: try without cookies
    print(f"[video.py] Tried browsers {tried_browsers}. Falling back to no-cookies.")
    opts = dict(base_opts)
    info, err = _try_download_with_opts(opts, url)
    if info:
        with yt_dlp.YoutubeDL(opts) as ydl_tmp:
            file_path = ydl_tmp.prepare_filename(info)
        root, _ = os.path.splitext(file_path)
        final = f"{root}.{merge_format}"
        return os.path.abspath(final)
    else:
        print(f"[video.py] Final attempt without cookies failed: {err}")
        return None
