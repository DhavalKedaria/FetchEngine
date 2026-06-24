import yt_dlp
import os
import requests

YOUTUBE_CLIENT_SETS = (
    ('android_vr', 'web_safari'),
    ('ios', 'android'),
    ('mweb', 'tv'),
)

def download_thumbnail_file(url, out_dir, progress_cb=None):
    os.makedirs(out_dir, exist_ok=True)

    base_opts = {
        'skip_download': True,
        'quiet': True,
        'noplaylist': True,
        'ignore_no_formats_error': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'outtmpl': os.path.join(out_dir, '%(title)s.%(ext)s'),
        'cachedir': False,
    }

    info = None
    last_error = None
    for clients in YOUTUBE_CLIENT_SETS:
        ydl_opts = {
            **base_opts,
            'extractor_args': {'youtube': {'player_client': list(clients)}},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            break
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            print(f"Thumbnail metadata retry needed for YouTube clients {clients}: {e}")

    if not info:
        if last_error:
            raise last_error
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

    r = requests.get(thumb_url, stream=True, timeout=20)
    r.raise_for_status()

    ext = '.jpg'
    ct = r.headers.get('Content-Type', '')
    if 'png' in ct:
        ext = '.png'
    elif 'webp' in ct:
        ext = '.webp'

    safe_title = "".join(ch for ch in title if ch.isalnum() or ch in " ._-").rstrip()
    out_path = os.path.join(out_dir, f"{safe_title}_thumbnail{ext}")

    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return out_path
