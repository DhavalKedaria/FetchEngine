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

    ydl_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'outtmpl': f'{pathname}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': preferredcodec,
            'preferredquality': quality if preferredcodec in ('mp3', 'aac', 'vorbis') else None,
        }],
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'quiet': True,
    }

    # Remove None entries in postprocessor dict (avoids warnings)
    if ydl_opts['postprocessors'][0]['preferredquality'] is None:
        del ydl_opts['postprocessors'][0]['preferredquality']

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = ydl.prepare_filename(info)
            # Convert final extension to requested one
            root, _ = os.path.splitext(base)
            final_ext = 'ogg' if preferredcodec == 'vorbis' else preferredcodec
            filename = f"{root}.{final_ext}"
            return os.path.abspath(filename)
    except Exception as e:
        print(f"Error during audio download: {e}")
        return None
