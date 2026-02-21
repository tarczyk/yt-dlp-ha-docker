#!/usr/bin/with-contenv bashio

PORT=$(bashio::config 'port')
export PORT="${PORT:-5000}"
export DOWNLOAD_DIR="/media/youtube_downloads"

exec python3 -m flask --app app run --host=0.0.0.0 --port="${PORT}"
