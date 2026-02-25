FROM python:3.14-alpine

RUN apk add --no-cache \
        curl \
        ffmpeg \
        nodejs \
        npm \
        unzip \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && addgroup -S appgroup \
    && adduser -S -G appgroup -h /home/appuser appuser \
    && mkdir -p /home/appuser \
    && chown appuser:appgroup /home/appuser

RUN mkdir -p /config/media && chown appuser:appgroup /config/media

WORKDIR /app

COPY yt-dlp-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup yt-dlp-api/app/ ./app/

USER appuser

EXPOSE 5000

CMD ["python", "-m", "flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5000"]
