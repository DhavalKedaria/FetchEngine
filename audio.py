import yt_dlp
import os

# audio_format: mp3|m4a|aac|wav|ogg|flac
def getaudio(url, pathname, audio_format='mp3', quality='320', progress_cb=None):
    os.makedirs(pathname, exist_ok=True)

    # Map yt-dlp/ffmpeg preferred codec names
    fmt = audio_format.lower()
    preferredcodec = fmt
    # some aliases
    if fmt == 'm4a':
        preferredcodec = 'm4a'
    elif fmt == 'aac':
        preferredcodec = 'aac'
    elif fmt == 'ogg':
        preferredcodec = 'vorbis'  # ogg container with vorbis
    elif fmt == 'wav':
        preferredcodec = 'wav'
    elif fmt == 'flac':
        preferredcodec = 'flac'
    else:
        preferredcodec = 'mp3'

    base_opts = {
        'format': 'bestaudio[acodec!=none]/best[acodec!=none]/bestaudio/best',
        'extractaudio': True,
        'outtmpl': os.path.join(pathname, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': preferredcodec,
            'preferredquality': quality if preferredcodec in ('mp3', 'aac', 'vorbis') else None,
        }],
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'quiet': True,
        'cachedir': False,
    }

    # Remove None entries in postprocessor dict (avoids warnings)
    if base_opts['postprocessors'][0]['preferredquality'] is None:
        del base_opts['postprocessors'][0]['preferredquality']

    youtube_client_sets = (
        ('android_vr', 'web_safari'),
        ('ios', 'android'),
        ('mweb', 'tv'),
    )

    try:
        last_error = None

        for clients in youtube_client_sets:
            ydl_opts = {
                **base_opts,
                'extractor_args': {'youtube': {'player_client': list(clients)}},
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    base = ydl.prepare_filename(info)
                    # Convert final extension to requested one
                    root, _ = os.path.splitext(base)
                    final_ext = 'ogg' if preferredcodec == 'vorbis' else preferredcodec
                    filename = f"{root}.{final_ext}"
                    return os.path.abspath(filename)
            except yt_dlp.utils.DownloadError as e:
                last_error = e
                print(f"Audio download retry needed for YouTube clients {clients}: {e}")

        if last_error:
            print(f"Error during audio download: {last_error}")
        return None
    except Exception as e:
        print(f"Error during audio download: {e}")
        return None
