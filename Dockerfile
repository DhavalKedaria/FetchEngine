FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Bake yt-dlp and its optional runtime helpers into the image. The app does not
# need internet access after the Docker image has been built.
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    python -m pip install --no-cache-dir --upgrade --pre "yt-dlp[default]"

COPY . .

EXPOSE 1500

CMD ["python", "app.py"]
