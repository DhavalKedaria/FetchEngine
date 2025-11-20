import yt_dlp
import os

# fmt: mp4|webm|mkv
def downloader(url, output_folder, fmt='mp4', resolution=1080, progress_cb=None):
    os.makedirs(output_folder, exist_ok=True)

    fmt = fmt.lower()
    merge_format = fmt if fmt in ('mp4', 'webm', 'mkv') else 'mp4'

    # Choose best video up to target height with best audio
    ydl_opts = {
        'format': f'bestvideo[height<={int(resolution)}]+bestaudio/best',
        'merge_output_format': merge_format,
        'outtmpl': f'{output_folder}/%(title)s.%(ext)s',
        'concurrent_fragment_downloads': 4,
        'noplaylist': True,
        'progress_hooks': [progress_cb] if progress_cb else [],
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': merge_format,
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            root, _ = os.path.splitext(file_path)
            wanted_ext = merge_format
            final = f"{root}.{wanted_ext}"
            return os.path.abspath(final)
    except yt_dlp.utils.DownloadError as e:
        print(f"Download error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
