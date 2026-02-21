ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache \
        curl \
        ffmpeg \
        nodejs \
        npm \
        python3 \
        py3-pip \
        unzip \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

RUN mkdir -p /media/youtube_downloads

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ ./app/
COPY yt-dlp-api/run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 5000

CMD ["/run.sh"]
