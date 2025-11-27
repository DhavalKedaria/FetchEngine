# Fetchengine

Fetchengine is a powerful, local web-based media downloader built with Python and Flask. It provides a simple interface to download videos, audio, subtitles, and thumbnails from YouTube and other supported platforms. By Dhaval Kedaria

## 🚀 Features

* **Cookies**: You can use Your Cookies
* **High-Quality Video Downloads**: Supports resolutions up to **4K** and various formats (MP4, etc.).
* **Versatile Audio Support**: Download audio tracks in multiple high-quality formats, including **MP3 (320kbps)** and **FLAC**.
* **Subtitle Extraction**: Easily download subtitles (SRT) by specifying the language code (e.g., `en`, `hi`).
* **Thumbnails**: Grab the best quality thumbnail available for the video.
* **Modular Design**: Built with specific modules for video, audio, and image handling.
* **Docker Support**: Includes a Dockerfile for containerized deployment.

## 🛠️ Tech Stack

* **Language**: Python
* **Backend Framework**: Flask
* **Media Processing**: FFmpeg
* **Frontend**: HTML/CSS (Jinja2 Templates)

## 📂 Project Structure

Based on the current source code, here is the structure of the application:

| Name | Type | Description |
| :--- | :--- | :--- |
| 📁 `templates/` | Folder | Contains HTML files for the web interface. |
| 📁 `download/` | Folder | Default directory where media is saved. |
| 📁 `__pycache__/` | Folder | Compiled Python files. |
| 📄 `app.py` | File | The main Flask application entry point. |
| 📄 `video.py` | File | Logic for handling video downloads and resolution switching. |
| 📄 `audio.py` | File | Logic for extracting and converting audio (MP3, FLAC). |
| 📄 `subtitles.py` | File | Logic for fetching and saving subtitle files. |
| 📄 `thumbnails.py` | File | Logic for retrieving high-quality thumbnails. |
| 📄 `requirements.txt` | File | List of Python dependencies. |
| 📄 `Dockerfile` | File | Configuration for building the Docker image. |
| ⚙️ `Server_start.bat` | Script | **One-click script to run the server on Windows.** |

## ⚙️ Prerequisites

Before running the application, ensure you have the following installed:

1.  **Python 3.x**: [Download Python](https://www.python.org/downloads/)
2.  **FFmpeg**: This is crucial for media conversion.
    * Download from [ffmpeg.org](https://ffmpeg.org/download.html).
    * **Important**: Make sure `ffmpeg` is added to your system's PATH environment variable.

## 📥 Installation

1.  Clone the repository or download the source code.
2.  Open a terminal in the project directory.
3.  Install the required Python packages:

```bash
pip install -r requirements.txt
```

## ▶️ How to Run

### Method 1: The Easy Way (Windows)
You can run the project directly without opening a terminal by double-clicking the batch file:

* Double-click **`Server_start.bat`**

### Method 2: Manual Start
Run the application using Python:

```bash
python app.py
```

### Accessing the App
Once the server is running, open your web browser and navigate to:

`http://localhost:1500`

---
*Note: This tool is for educational purposes. Please respect copyright laws and terms of service of the websites you download from.*